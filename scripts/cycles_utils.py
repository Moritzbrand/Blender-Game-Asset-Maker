# Purpose: cycles utils module.
# Example: import cycles_utils
import bpy


class CyclesUtils:
    @staticmethod
    def _refresh_cycles_devices(cprefs):
        try:
            cprefs.refresh_devices()
            return
        except Exception:
            pass

        try:
            cprefs.get_devices()
        except Exception:
            pass

    @staticmethod
    def _iter_cycles_devices(cprefs):
        devices = getattr(cprefs, "devices", [])
        for entry in devices:
            if hasattr(entry, "use") and hasattr(entry, "type"):
                yield entry
            else:
                try:
                    for sub in entry:
                        if hasattr(sub, "use") and hasattr(sub, "type"):
                            yield sub
                except TypeError:
                    pass

    @staticmethod
    def configure_cycles(scene, samples=512):
        scene.render.engine = 'CYCLES'

        backend_used = None
        denoiser_used = 'OPENIMAGEDENOISE'

        prefs = bpy.context.preferences
        cycles_addon = prefs.addons.get("cycles")
        cprefs = None

        if cycles_addon is not None:
            cprefs = cycles_addon.preferences

            for backend in ("OPTIX", "CUDA", "HIP", "ONEAPI", "METAL"):
                try:
                    cprefs.compute_device_type = backend
                    CyclesUtils._refresh_cycles_devices(cprefs)

                    gpu_found = False
                    for device in CyclesUtils._iter_cycles_devices(cprefs):
                        use_device = getattr(device, "type", None) != 'CPU'
                        device.use = use_device
                        if use_device:
                            gpu_found = True

                    if gpu_found:
                        scene.cycles.device = 'GPU'
                        backend_used = backend
                        break
                except Exception:
                    continue

        if backend_used is None:
            scene.cycles.device = 'CPU'

        print("Backend:", backend_used)
        if cprefs is not None:
            for device in CyclesUtils._iter_cycles_devices(cprefs):
                print(device.name, device.type, device.use)

        scene.cycles.samples = samples
        scene.cycles.preview_samples = min(samples, 64)

        if hasattr(scene.cycles, "use_adaptive_sampling"):
            scene.cycles.use_adaptive_sampling = False

        if hasattr(scene.cycles, "use_denoising"):
            scene.cycles.use_denoising = True

        if backend_used == "OPTIX":
            denoiser_used = 'OPTIX'
        else:
            denoiser_used = 'OPENIMAGEDENOISE'

        if hasattr(scene.cycles, "denoiser"):
            try:
                scene.cycles.denoiser = denoiser_used
            except Exception:
                pass

        if hasattr(scene.cycles, "use_preview_denoising"):
            scene.cycles.use_preview_denoising = True

        if hasattr(scene.cycles, "preview_denoiser"):
            try:
                scene.cycles.preview_denoiser = denoiser_used
            except Exception:
                pass

        if hasattr(scene.cycles, "denoising_use_gpu"):
            try:
                scene.cycles.denoising_use_gpu = backend_used is not None
            except Exception:
                pass

        if hasattr(scene.cycles, "preview_denoising_use_gpu"):
            try:
                scene.cycles.preview_denoising_use_gpu = backend_used is not None
            except Exception:
                pass

        scene.view_settings.view_transform = "Standard"
        scene.view_settings.look = "None"

        return {
            "engine": scene.render.engine,
            "device": scene.cycles.device,
            "backend": backend_used if backend_used else "CPU",
            "samples": scene.cycles.samples,
            "denoiser": denoiser_used,
            "denoising_use_gpu": getattr(scene.cycles, "denoising_use_gpu", None),
        }
