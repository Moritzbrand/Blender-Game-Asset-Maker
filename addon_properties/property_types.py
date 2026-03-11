import bpy


class ScenePropertyDefinition:
    def __init__(self, attr_name: str, name: str, description: str, options=None):
        self.attr_name = attr_name
        self.name = name
        self.description = description
        self.options = options or set()

    def register(self):
        raise NotImplementedError("Subclasses must implement register()")

    def unregister(self):
        if hasattr(bpy.types.Scene, self.attr_name):
            delattr(bpy.types.Scene, self.attr_name)


class BoolSceneProperty(ScenePropertyDefinition):
    def __init__(self, attr_name: str, name: str, description: str, default=False, options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.BoolProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                options=self.options,
            ),
        )


class EnumSceneProperty(ScenePropertyDefinition):
    def __init__(self, attr_name: str, name: str, description: str, items, default=None, update=None, options=None):
        super().__init__(attr_name, name, description, options=options)
        self.items = items
        self.default = default
        self.update = update

    def register(self):
        enum_kwargs = {
            "name": self.name,
            "description": self.description,
            "items": self.items,
            "options": self.options,
        }
        if self.default is not None and not callable(self.items):
            enum_kwargs["default"] = self.default
        if self.update is not None:
            enum_kwargs["update"] = self.update

        setattr(bpy.types.Scene, self.attr_name, bpy.props.EnumProperty(**enum_kwargs))


class IntSceneProperty(ScenePropertyDefinition):
    def __init__(self, attr_name: str, name: str, description: str, default=0, min=0, max=100, options=None, subtype='NONE'):
        super().__init__(attr_name, name, description, options=options)
        self.default = default
        self.min = min
        self.max = max
        self.subtype = subtype

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.IntProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                min=self.min,
                max=self.max,
                subtype=self.subtype,
                options=self.options,
            ),
        )


class FloatSceneProperty(ScenePropertyDefinition):
    def __init__(self, attr_name: str, name: str, description: str, default=0.0, min=0.0, max=1.0, subtype='NONE', options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default
        self.min = min
        self.max = max
        self.subtype = subtype

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.FloatProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                min=self.min,
                max=self.max,
                subtype=self.subtype,
                options=self.options,
            ),
        )


class PathSceneProperty(ScenePropertyDefinition):
    def __init__(self, attr_name: str, name: str, description: str, default="", subtype='NONE', options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default
        self.subtype = subtype

    def register(self):
        property_options = set(self.options)
        property_options.add('PATH_SUPPORTS_BLEND_RELATIVE')
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.StringProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                subtype=self.subtype,
                options=property_options,
            ),
        )


class StringSceneProperty(ScenePropertyDefinition):
    def __init__(self, attr_name: str, name: str, description: str, default="", options=None):
        super().__init__(attr_name, name, description, options=options)
        self.default = default

    def register(self):
        setattr(
            bpy.types.Scene,
            self.attr_name,
            bpy.props.StringProperty(
                name=self.name,
                description=self.description,
                default=self.default,
                options=self.options,
            ),
        )
