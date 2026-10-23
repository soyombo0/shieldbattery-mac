// Stand-in for DXMT's winemetal.so that fixes two leaks costing StarCraft about 20 GB of memory
// per hour of play (DXMT issues #236 and #237), until macOS runs out of memory and WindowServer
// hangs. It loads the real library (renamed winemetal.orig.so), exports a copy of its unix call
// tables and changes two entries:
//
// - _WMTGetDisplayDescription (#236), called many times per frame, never releases the ColorSync
//   profiles it creates or the tag data it copies. Replaced by the same code with the releases.
// - _WMTQueryDisplaySettingForLayer (#237) gets autoreleased AppKit objects on a thread without an
//   autorelease pool, so they are never freed. Wrapped in a pool.
//
// Every other entry is the original function. Slot numbers are for DXMT 7c8dee1, the Sikarugir
// template's build; patch_winemetal.py checks them against the actual binary before installing.
#import <AppKit/AppKit.h>
#import <ColorSync/ColorSync.h>
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define TABLE_SIZE 146
#define SLOT_GET_DISPLAY_DESCRIPTION 96
#define SLOT_QUERY_DISPLAY_SETTING_FOR_LAYER 101

typedef int NTSTATUS;
typedef NTSTATUS (*unixcall)(void *);

__attribute__((visibility("default"))) const void *__wine_unix_call_funcs[TABLE_SIZE];
__attribute__((visibility("default"))) const void *__wine_unix_call_wow64_funcs[TABLE_SIZE];

static unixcall orig_query_display_setting_for_layer[2];

// From DXMT 7c8dee1: src/winemetal/winemetal.h and winemetal_thunks.h.
struct WMTDisplayDescription {
  float red_primaries[2];
  float blue_primaries[2];
  float green_primaries[2];
  float white_points[2];
  float maximum_edr_color_component_value;
  float maximum_potential_edr_color_component_value;
  float maximum_reference_edr_color_component_value;
};

struct unixcall_generic_obj_ptr_noret {
  uint64_t handle;
  void *ptr;
};

typedef struct {
  uint32_t sig; // 'XYZ '
  uint32_t reserved;
  int32_t x;
  int32_t y;
  int32_t z;
} icc_XYZ_t;

static bool
chromaticity_xy(ColorSyncProfileRef profile, CFStringRef tag, float *out_x, float *out_y) {
  CFDataRef tag_data = ColorSyncProfileCopyTag(profile, tag);
  if (!tag_data)
    return false;
  bool ok = false;
  const icc_XYZ_t *data = (const icc_XYZ_t *)CFDataGetBytePtr(tag_data);
  if (CFDataGetLength(tag_data) == sizeof(icc_XYZ_t) && data->sig == 0x205a5958) {
    double X = (int32_t)__builtin_bswap32(data->x) / 65536.0;
    double Y = (int32_t)__builtin_bswap32(data->y) / 65536.0;
    double Z = (int32_t)__builtin_bswap32(data->z) / 65536.0;
    *out_x = X / (X + Y + Z);
    *out_y = Y / (X + Y + Z);
    ok = true;
  }
  CFRelease(tag_data);
  return ok;
}

static bool
display_color_gamut(ColorSyncProfileRef profile, struct WMTDisplayDescription *desc) {
  return chromaticity_xy(profile, kColorSyncSigMediaWhitePointTag, &desc->white_points[0], &desc->white_points[1]) &&
         chromaticity_xy(profile, kColorSyncSigRedColorantTag, &desc->red_primaries[0], &desc->red_primaries[1]) &&
         chromaticity_xy(profile, kColorSyncSigGreenColorantTag, &desc->green_primaries[0], &desc->green_primaries[1]) &&
         chromaticity_xy(profile, kColorSyncSigBlueColorantTag, &desc->blue_primaries[0], &desc->blue_primaries[1]);
}

static NTSTATUS
get_display_description(void *obj) {
  struct unixcall_generic_obj_ptr_noret *params = obj;
  CGDirectDisplayID display_id = (CGDirectDisplayID)params->handle;
  struct WMTDisplayDescription *desc = params->ptr;
  @autoreleasepool {
    ColorSyncProfileRef profile = ColorSyncProfileCreateWithDisplayID(display_id);
    if (!profile || !display_color_gamut(profile, desc)) {
      ColorSyncProfileRef generic = ColorSyncProfileCreateWithName(kColorSyncGenericRGBProfile);
      if (generic) {
        display_color_gamut(generic, desc);
        CFRelease(generic);
      }
    }
    if (profile)
      CFRelease(profile);

    NSScreen *screen = nil;
    for (NSScreen *s in [NSScreen screens]) {
      if ([[[s deviceDescription] objectForKey:@"NSScreenNumber"] unsignedIntValue] == display_id) {
        screen = s;
        break;
      }
    }
    if (screen) {
      desc->maximum_edr_color_component_value = [screen maximumExtendedDynamicRangeColorComponentValue];
      desc->maximum_reference_edr_color_component_value =
          [screen maximumReferenceExtendedDynamicRangeColorComponentValue];
      desc->maximum_potential_edr_color_component_value =
          [screen maximumPotentialExtendedDynamicRangeColorComponentValue];
    } else {
      desc->maximum_edr_color_component_value = 1.0;
      desc->maximum_reference_edr_color_component_value = 0.0;
      desc->maximum_potential_edr_color_component_value = 1.0;
    }
  }
  return 0;
}

static NTSTATUS
query_display_setting_for_layer(void *obj) {
  @autoreleasepool {
    return orig_query_display_setting_for_layer[0](obj);
  }
}

static NTSTATUS
query_display_setting_for_layer_wow64(void *obj) {
  @autoreleasepool {
    return orig_query_display_setting_for_layer[1](obj);
  }
}

__attribute__((constructor)) static void
load_original(void) {
  Dl_info info;
  char path[4096];
  if (!dladdr((void *)&__wine_unix_call_funcs, &info) || !strrchr(info.dli_fname, '/'))
    abort();
  snprintf(path, sizeof(path), "%.*s/winemetal.orig.so", (int)(strrchr(info.dli_fname, '/') - info.dli_fname),
           info.dli_fname);
  void *orig = dlopen(path, RTLD_NOW | RTLD_LOCAL);
  const void **funcs = orig ? dlsym(orig, "__wine_unix_call_funcs") : NULL;
  const void **wow64_funcs = orig ? dlsym(orig, "__wine_unix_call_wow64_funcs") : NULL;
  if (!funcs || !wow64_funcs) {
    fprintf(stderr, "winemetal_leakfix: can't load %s: %s\n", path, dlerror());
    abort();
  }
  memcpy(__wine_unix_call_funcs, funcs, sizeof(__wine_unix_call_funcs));
  memcpy(__wine_unix_call_wow64_funcs, wow64_funcs, sizeof(__wine_unix_call_wow64_funcs));

  orig_query_display_setting_for_layer[0] = (unixcall)funcs[SLOT_QUERY_DISPLAY_SETTING_FOR_LAYER];
  orig_query_display_setting_for_layer[1] = (unixcall)wow64_funcs[SLOT_QUERY_DISPLAY_SETTING_FOR_LAYER];
  __wine_unix_call_funcs[SLOT_GET_DISPLAY_DESCRIPTION] = get_display_description;
  __wine_unix_call_wow64_funcs[SLOT_GET_DISPLAY_DESCRIPTION] = get_display_description;
  __wine_unix_call_funcs[SLOT_QUERY_DISPLAY_SETTING_FOR_LAYER] = query_display_setting_for_layer;
  __wine_unix_call_wow64_funcs[SLOT_QUERY_DISPLAY_SETTING_FOR_LAYER] = query_display_setting_for_layer_wow64;
}
