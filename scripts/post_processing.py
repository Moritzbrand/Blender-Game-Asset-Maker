# Purpose: post processing module.
# Example: import post_processing
from collections import deque

from .image_utils import ImageUtils


class BakeFillStrategy:
    def is_default_pixel(self, pixel_rgba, default_pixel, tolerance):
        return all(abs(pixel_rgba[channel] - default_pixel[channel]) <= tolerance for channel in range(4))

    def blend_neighbor_pixels(self, neighbor_pixels):
        if not neighbor_pixels:
            return None

        channel_count = 4
        blended_pixel = [0.0] * channel_count
        for neighbor_pixel in neighbor_pixels:
            for channel_index in range(channel_count):
                blended_pixel[channel_index] += neighbor_pixel[channel_index]

        sample_count = float(len(neighbor_pixels))
        return tuple(channel_value / sample_count for channel_value in blended_pixel)


class PostBakeHoleStitchPass:
    DEFAULT_PIXELS_BY_TEXTURE_KEY = {
        "normal": (0.5, 0.5, 1.0, 1.0),
        "roughness": (1.0, 1.0, 1.0, 1.0),
        "orm": (1.0, 1.0, 1.0, 1.0),
    }

    def __init__(self, default_tolerance=0.001):
        self.default_tolerance = float(default_tolerance)
        self.strategy_by_texture_key = {}
        self.default_strategy = BakeFillStrategy()

    def run(self, image, target_object, texture_key=""):
        ImageUtils.require_image(image, "image")
        if target_object is None or getattr(target_object, "type", None) != 'MESH':
            return False

        width, height = int(image.size[0]), int(image.size[1])
        if width <= 0 or height <= 0:
            return False

        covered_mask = self._build_covered_uv_mask(target_object, width, height)
        if not any(covered_mask):
            return False

        pixels = list(image.pixels)
        strategy = self.strategy_by_texture_key.get(texture_key, self.default_strategy)
        default_pixel = self._resolve_default_pixel(texture_key, image)

        hole_mask = self._build_hole_mask(
            pixels=pixels,
            covered_mask=covered_mask,
            width=width,
            height=height,
            strategy=strategy,
            default_pixel=default_pixel,
        )
        if not any(hole_mask):
            return False

        repaired_pixels = self._fill_holes_from_neighbors(
            pixels=pixels,
            covered_mask=covered_mask,
            hole_mask=hole_mask,
            width=width,
            height=height,
            strategy=strategy,
        )
        if repaired_pixels is None:
            return False

        ImageUtils.write_pixels_to_image(image, repaired_pixels)
        return True

    def _resolve_default_pixel(self, texture_key, image):
        if texture_key in self.DEFAULT_PIXELS_BY_TEXTURE_KEY:
            return self.DEFAULT_PIXELS_BY_TEXTURE_KEY[texture_key]

        generated_color = tuple(getattr(image, "generated_color", (0.0, 0.0, 0.0, 1.0)))
        if len(generated_color) < 4:
            return (0.0, 0.0, 0.0, 1.0)
        return generated_color[0:4]

    def _build_hole_mask(self, pixels, covered_mask, width, height, strategy, default_pixel):
        candidate_mask = [False] * (width * height)
        for pixel_index in range(width * height):
            if not covered_mask[pixel_index]:
                continue
            start = pixel_index * 4
            pixel_rgba = (
                pixels[start],
                pixels[start + 1],
                pixels[start + 2],
                pixels[start + 3],
            )
            if strategy.is_default_pixel(pixel_rgba, default_pixel, self.default_tolerance):
                candidate_mask[pixel_index] = True

        return self._filter_candidates_to_connected_holes(candidate_mask, covered_mask, width, height)

    def _filter_candidates_to_connected_holes(self, candidate_mask, covered_mask, width, height):
        hole_mask = [False] * len(candidate_mask)
        visited = [False] * len(candidate_mask)

        for pixel_index, is_candidate in enumerate(candidate_mask):
            if not is_candidate or visited[pixel_index]:
                continue

            queue = deque([pixel_index])
            visited[pixel_index] = True
            component_pixels = []
            touches_non_default_texel = False

            while queue:
                current_index = queue.popleft()
                component_pixels.append(current_index)
                current_x = current_index % width
                current_y = current_index // width

                for neighbor_index in self._neighbor_indices(current_x, current_y, width, height):
                    if not covered_mask[neighbor_index]:
                        continue

                    if candidate_mask[neighbor_index]:
                        if not visited[neighbor_index]:
                            visited[neighbor_index] = True
                            queue.append(neighbor_index)
                    else:
                        touches_non_default_texel = True

            if touches_non_default_texel:
                for component_index in component_pixels:
                    hole_mask[component_index] = True

        return hole_mask

    def _fill_holes_from_neighbors(self, pixels, covered_mask, hole_mask, width, height, strategy):
        repaired_pixels = list(pixels)
        valid_mask = [covered_mask[index] and not hole_mask[index] for index in range(width * height)]
        unresolved_holes = {index for index, is_hole in enumerate(hole_mask) if is_hole}

        if not unresolved_holes:
            return None

        while unresolved_holes:
            filled_in_this_pass = []

            for hole_index in list(unresolved_holes):
                hole_x = hole_index % width
                hole_y = hole_index // width
                neighbor_pixels = []

                for neighbor_index in self._neighbor_indices(hole_x, hole_y, width, height):
                    if not valid_mask[neighbor_index]:
                        continue

                    start = neighbor_index * 4
                    neighbor_pixels.append((
                        repaired_pixels[start],
                        repaired_pixels[start + 1],
                        repaired_pixels[start + 2],
                        repaired_pixels[start + 3],
                    ))

                blended_pixel = strategy.blend_neighbor_pixels(neighbor_pixels)
                if blended_pixel is None:
                    continue

                filled_in_this_pass.append((hole_index, blended_pixel))

            if not filled_in_this_pass:
                break

            for hole_index, blended_pixel in filled_in_this_pass:
                start = hole_index * 4
                repaired_pixels[start:start + 4] = blended_pixel
                valid_mask[hole_index] = True
                unresolved_holes.remove(hole_index)

        return repaired_pixels

    def _build_covered_uv_mask(self, mesh_object, width, height):
        uv_layer = getattr(getattr(mesh_object, "data", None), "uv_layers", None)
        if uv_layer is None or uv_layer.active is None:
            return [True] * (width * height)

        uv_data = uv_layer.active.data
        polygons = getattr(mesh_object.data, "polygons", [])
        covered_mask = [False] * (width * height)

        for polygon in polygons:
            loop_indices = list(polygon.loop_indices)
            if len(loop_indices) < 3:
                continue

            uv_points = [uv_data[loop_index].uv for loop_index in loop_indices]
            for tri_start in range(1, len(uv_points) - 1):
                triangle = (uv_points[0], uv_points[tri_start], uv_points[tri_start + 1])
                self._rasterize_uv_triangle(triangle, covered_mask, width, height)

        return covered_mask

    def _rasterize_uv_triangle(self, triangle_uvs, covered_mask, width, height):
        pixel_triangle = [
            ((uv[0] % 1.0) * (width - 1), (uv[1] % 1.0) * (height - 1))
            for uv in triangle_uvs
        ]

        min_x = max(0, int(min(point[0] for point in pixel_triangle)))
        max_x = min(width - 1, int(max(point[0] for point in pixel_triangle)) + 1)
        min_y = max(0, int(min(point[1] for point in pixel_triangle)))
        max_y = min(height - 1, int(max(point[1] for point in pixel_triangle)) + 1)

        for pixel_y in range(min_y, max_y + 1):
            for pixel_x in range(min_x, max_x + 1):
                if self._point_in_triangle((pixel_x + 0.5, pixel_y + 0.5), pixel_triangle):
                    covered_mask[pixel_y * width + pixel_x] = True

    @staticmethod
    def _point_in_triangle(point, triangle):
        (ax, ay), (bx, by), (cx, cy) = triangle
        px, py = point

        denominator = ((by - cy) * (ax - cx) + (cx - bx) * (ay - cy))
        if abs(denominator) < 1e-12:
            return False

        w1 = ((by - cy) * (px - cx) + (cx - bx) * (py - cy)) / denominator
        w2 = ((cy - ay) * (px - cx) + (ax - cx) * (py - cy)) / denominator
        w3 = 1.0 - w1 - w2

        epsilon = -1e-6
        return w1 >= epsilon and w2 >= epsilon and w3 >= epsilon

    @staticmethod
    def _neighbor_indices(x, y, width, height):
        for offset_y in (-1, 0, 1):
            for offset_x in (-1, 0, 1):
                if offset_x == 0 and offset_y == 0:
                    continue
                nx = x + offset_x
                ny = y + offset_y
                if 0 <= nx < width and 0 <= ny < height:
                    yield ny * width + nx
