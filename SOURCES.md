# Protocol provenance

This prototype adapts the AlienFX v4 command layout and volatile transaction
sequence from the GPL-3.0 AlienFX Linux SDK, credited to tr1xem and the original
T-Troll AlienFX tools project. The prototype is distributed under GPL-3.0;
see LICENSE.

- https://github.com/tr1xem/alienfx-linux
- Inspected commit: `a16a4164d98d948cd294f3164fa5862cf08f8d12`
- `AlienFX-SDK/include/alienfx_control.h`: COMMV4_control, COMMV4_setOneColor.
- `AlienFX-SDK/src/AlienFX_SDK.cpp`: Reset, SetMultiColor, UpdateColors,
  GetDeviceStatus, API v4 device detection.
- `AlienFX-SDK/src/libusb_helper.cpp`: HIDAPI output and input report transport.
- Original upstream: https://github.com/T-Troll/alienfx-tools

The local `/usr/include/hidapi/hidapi.h` documents the transport interface used
through Python ctypes. This implementation requires ready status 0x21 before
writes rather than accepting every nonbusy response. An explicit experimental
`--allow-zero-status` option accepts a full 34-byte zero report, as observed
on this machine; upstream `IsDeviceReady` also permits zero status to proceed.
No upstream probing loops,
power features, persistent saves, or device resets are included.

The optional action method follows `EffectController::ScanZones` (one zone only)
and `LightFX.cpp` from https://github.com/tr1xem/AWCC: explicit undimming,
animation 0 start, zone selection, static RGB action, and play without save.
The same source defines explicit status query `03 20 01`, which produced a
structured response on this machine. We retain HIDAPI transport, already shown
to deliver that query successfully.
