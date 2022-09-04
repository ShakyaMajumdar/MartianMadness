import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import NodePath, WindowProperties


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

        self.player_node = NodePath("player_node")
        self.player_node.reparent_to(self.render)
        self.camera.reparent_to(self.player_node)
        self.player_node.set_pos(0, 0, 1)

        self.task_mgr.add(self.mouse_look_task, "mouse_look_task")

        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)

        self.accept("aspectRatioChanged", self.set_center)
        self.accept("escape", sys.exit)

    def set_center(self):
        self.center = (self.win.getXSize() // 2, self.win.getYSize() // 2)

    def mouse_look_task(self, _task):
        mx = self.mouseWatcherNode.getMouseX()
        my = self.mouseWatcherNode.getMouseY()
        self.rot_h += -1 * self.mouse_sensitivity * mx
        self.rot_v += self.mouse_sensitivity * my
        self.rot_v = min(90, max(-90, self.rot_v))
        self.player_node.set_hpr(self.rot_h, self.rot_v, 0)
        self.win.movePointer(0, *self.center)
        return Task.cont


game = Game()
game.run()
