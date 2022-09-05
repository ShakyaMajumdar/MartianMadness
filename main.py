import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import NodePath, WindowProperties, PointLight, KeyboardButton, Vec3


class Game(ShowBase):
    def __init__(self):
        super().__init__()

        self.center = None
        self.set_center()

        self.mouse_sensitivity = 30

        self.rot_v = 0
        self.rot_h = 0

        self.environment = self.loader.load_model("assets/models/ground.bam")
        self.environment.reparent_to(self.render)

        self.light = self.render.attach_new_node(PointLight('light'))
        self.light.set_pos(0, 0, 10)
        self.render.set_light(self.light)

        self.player_node = NodePath("player_node")
        self.player_node.reparent_to(self.render)
        self.camera.reparent_to(self.player_node)
        self.player_node.set_pos(0, 0, 1)

        self.task_mgr.add(self.mouse_look_task, "mouse_look_task")
        self.task_mgr.add(self.player_movement_task, "player_movement_task")

        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)

        self.accept("aspectRatioChanged", self.set_center)
        self.accept("escape", sys.exit)

    def set_center(self):
        self.center = (self.win.getXSize() // 2, self.win.getYSize() // 2)

    def mouse_look_task(self, _task):
        if self.mouseWatcherNode.hasMouse():
            mx = self.mouseWatcherNode.getMouseX()
            my = self.mouseWatcherNode.getMouseY()
            self.rot_h += -1 * self.mouse_sensitivity * mx
            self.rot_v += self.mouse_sensitivity * my
            self.rot_v = min(90, max(-90, self.rot_v))
            self.player_node.set_hpr(self.rot_h, 0, 0)
            self.camera.set_p(self.rot_v)
        self.win.movePointer(0, *self.center)
        return Task.cont

    def player_movement_task(self, _task):
        velocity = Vec3(0, 0, 0)
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("w")):
            velocity.y = 0.5
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("s")):
            velocity.y = -0.5
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("d")):
            velocity.x = 0.5
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("a")):
            velocity.x = -0.5
        if self.mouseWatcherNode.is_button_down(KeyboardButton.space()):
            velocity.z = 0.5
        if self.mouseWatcherNode.is_button_down(KeyboardButton.shift()):
            velocity.z = -0.5
        self.player_node.set_pos(self.player_node, *velocity)
        return Task.cont



game = Game()
game.run()
