# Purpose: image utils module.
# Example: import image_utils
import bpy


class ImageUtils:
    @classmethod
    def require_image(cls, image, argument_name):
        if image is None:
            raise ValueError(f"{argument_name} is required")

    @classmethod
    def require_matching_image_sizes(cls, images, error_message):
        image_sizes = [tuple(image.size) for image in images]
        first_image_size = image_sizes[0]

        for current_image_size in image_sizes[1:]:
            if current_image_size != first_image_size:
                raise ValueError(error_message)

        return first_image_size

    @classmethod
    def configure_image_for_png_output(cls, image, color_mode='RGBA', compression=15, channel_packed=False):
        try:
            image.file_format = 'PNG'
        except Exception:
            pass

        try:
            image.alpha_mode = 'CHANNEL_PACKED' if channel_packed else 'STRAIGHT'
        except Exception:
            pass

        try:
            image["gameready_color_mode"] = str(color_mode)
            image["gameready_compression"] = int(compression)
        except Exception:
            pass

    @classmethod
    def _get_image_color_mode(cls, image):
        try:
            return str(image.get("gameready_color_mode", "RGBA"))
        except Exception:
            return "RGBA"

    @classmethod
    def _get_image_compression(cls, image, scene=None):
        try:
            return int(image.get("gameready_compression", 15))
        except Exception:
            pass

        if scene is not None:
            try:
                return int(getattr(scene, "gameready_texture_compression", 15))
            except Exception:
                pass

        return 15

    @classmethod
    def save_image_if_possible(cls, image, scene=None):
        try:
            filepath = getattr(image, "filepath_raw", "") or getattr(image, "filepath", "")
            if not filepath:
                return
        except Exception:
            return

        scene = scene or getattr(bpy.context, "scene", None)
        if scene is None:
            try:
                image.save()
            except Exception:
                pass
            return

        settings = scene.render.image_settings
        backup = {
            "file_format": getattr(settings, "file_format", 'PNG'),
            "color_mode": getattr(settings, "color_mode", 'RGBA'),
            "color_depth": getattr(settings, "color_depth", '8'),
            "compression": getattr(settings, "compression", 15),
            "color_management": getattr(settings, "color_management", 'FOLLOW_SCENE'),
        }

        try:
            settings.file_format = 'PNG'
            if hasattr(settings, "color_mode"):
                settings.color_mode = cls._get_image_color_mode(image)
            if hasattr(settings, "color_depth"):
                settings.color_depth = '8'
            if hasattr(settings, "compression"):
                settings.compression = cls._get_image_compression(image, scene)
            if hasattr(settings, "color_management"):
                settings.color_management = 'FOLLOW_SCENE'
            image.save_render(filepath=filepath, scene=scene)
        except Exception:
            try:
                image.save()
            except Exception:
                pass
        finally:
            try:
                settings.file_format = backup["file_format"]
            except Exception:
                pass
            try:
                settings.color_mode = backup["color_mode"]
            except Exception:
                pass
            try:
                settings.color_depth = backup["color_depth"]
            except Exception:
                pass
            try:
                settings.compression = backup["compression"]
            except Exception:
                pass
            try:
                settings.color_management = backup["color_management"]
            except Exception:
                pass

    @classmethod
    def write_pixels_to_image(cls, image, image_pixels, scene=None):
        image.pixels[:] = image_pixels
        image.update()
        cls.save_image_if_possible(image, scene=scene)

    @classmethod
    def flip_normal_map_y(cls, image, scene=None):
        cls.require_image(image, "image")

        image_pixels = list(image.pixels)
        if not image_pixels:
            return image

        for pixel_start_index in range(0, len(image_pixels), 4):
            green_channel_index = pixel_start_index + 1
            image_pixels[green_channel_index] = 1.0 - image_pixels[green_channel_index]

        cls.write_pixels_to_image(image, image_pixels, scene=scene)
        return image

    @classmethod
    def combine_orm_images(
        cls,
        ao_image,
        roughness_image,
        metallic_image,
        target_image,
        scene=None,
    ):
        cls.require_image(ao_image, "ao_image")
        cls.require_image(roughness_image, "roughness_image")
        cls.require_image(metallic_image, "metallic_image")
        cls.require_image(target_image, "target_image")

        cls.require_matching_image_sizes(
            images=[ao_image, roughness_image, metallic_image, target_image],
            error_message="All ORM images must have the same size",
        )

        ambient_occlusion_pixels = list(ao_image.pixels)
        roughness_pixels = list(roughness_image.pixels)
        metallic_pixels = list(metallic_image.pixels)
        combined_orm_pixels = [0.0] * len(ambient_occlusion_pixels)

        for pixel_start_index in range(0, len(combined_orm_pixels), 4):
            combined_orm_pixels[pixel_start_index + 0] = ambient_occlusion_pixels[pixel_start_index + 0]
            combined_orm_pixels[pixel_start_index + 1] = roughness_pixels[pixel_start_index + 0]
            combined_orm_pixels[pixel_start_index + 2] = metallic_pixels[pixel_start_index + 0]
            combined_orm_pixels[pixel_start_index + 3] = 1.0

        cls.configure_image_for_png_output(
            target_image,
            color_mode='RGB',
            compression=cls._get_image_compression(target_image, scene),
            channel_packed=True,
        )
        cls.write_pixels_to_image(target_image, combined_orm_pixels, scene=scene)

    @classmethod
    def combine_rgb_and_alpha_images(
        cls,
        rgb_image,
        alpha_image,
        target_image,
        scene=None,
    ):
        cls.require_image(rgb_image, "rgb_image")
        cls.require_image(alpha_image, "alpha_image")
        cls.require_image(target_image, "target_image")

        cls.require_matching_image_sizes(
            images=[rgb_image, alpha_image, target_image],
            error_message="All images must have the same size",
        )

        rgb_pixels = list(rgb_image.pixels)
        alpha_pixels = list(alpha_image.pixels)
        combined_rgba_pixels = [0.0] * len(rgb_pixels)

        for pixel_start_index in range(0, len(rgb_pixels), 4):
            combined_rgba_pixels[pixel_start_index + 0] = rgb_pixels[pixel_start_index + 0]
            combined_rgba_pixels[pixel_start_index + 1] = rgb_pixels[pixel_start_index + 1]
            combined_rgba_pixels[pixel_start_index + 2] = rgb_pixels[pixel_start_index + 2]
            combined_rgba_pixels[pixel_start_index + 3] = alpha_pixels[pixel_start_index + 0]

        cls.configure_image_for_png_output(
            target_image,
            color_mode='RGBA',
            compression=cls._get_image_compression(target_image, scene),
            channel_packed=False,
        )
        cls.write_pixels_to_image(target_image, combined_rgba_pixels, scene=scene)

    @classmethod
    def debug_grayscale_range(cls, image, label="Image"):
        if image is None:
            print(f"{label}: image is None")
            return

        image_pixels = list(image.pixels)
        grayscale_values = image_pixels[0::4]

        if not grayscale_values:
            print(f"{label}: no pixels found")
            return

        print(
            f"{label}: value min={min(grayscale_values):.6f}, "
            f"max={max(grayscale_values):.6f}"
        )
