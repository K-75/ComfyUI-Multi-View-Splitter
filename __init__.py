from aiohttp import web
from .nodes import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

# Cache for storing images by node ID
_image_cache = {}
_image_size_cache = {"width": 0, "height": 0}


def get_cache():
    return _image_cache


def get_size_cache():
    return _image_size_cache


WEB_DIRECTORY = "./web"


__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]


# Register API routes - try immediate, fall back to deferred
import server


def _register_routes():
    ps = getattr(server.PromptServer, "instance", None)
    if ps is None:
        return False

    @ps.routes.get("/local_reference/get_image_size")
    async def get_image_size(request):
        size_cache = get_size_cache()
        return web.json_response(size_cache)

    @ps.routes.get("/local_reference/get_image")
    async def get_image(request):
        cache = get_cache()
        image_data = cache.get("latest")
        if image_data is None:
            return web.Response(status=404, text="Image not found")
        return web.Response(
            body=image_data,
            content_type="image/png",
            headers={"Cache-Control": "no-cache"},
        )

    return True


if not _register_routes():
    # Defer route registration until server is ready
    original_init = server.PromptServer.__init__

    def _patched_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        _register_routes()

    server.PromptServer.__init__ = _patched_init
