import sys

from direct.actor.Actor import Actor
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import *


class Game(ShowBase):
    def __init__(self):
        super().__init__()

        self.center = None
        self.set_center()

        self.mouse_sensitivity = 30

        self.rot_v = 0
        self.rot_h = 0

        self.environment = GeoMipTerrain("terrain")
        self.environment.setHeightfield("assets/hm.jpg")

        self.light = self.render.attach_new_node(PointLight('light'))
        self.light.set_pos(0, 0, 10)
        self.render.set_light(self.light)

        self.cTrav = CollisionTraverser()

        self.player_node = NodePath("player_node")
        self.player_node.reparent_to(self.render)
        self.player_cam = Camera("player_cam")
        self.player_camera = self.player_node.attachNewNode(self.player_cam)
        self.player_camera.set_pos(0, 0.35, 1.75)

        self.player_actor = Actor("assets/models/player.bam")
        self.player_actor.reparent_to(self.player_node)
        self.player_node.set_pos(0, 0, 1)
        self.player_actor.loop("Idle")

        # Set self.environment properties
        self.environment.setBlockSize(8)
        self.environment.setNear(40)
        self.environment.setFar(100)
        self.environment.setFocalPoint(self.player_camera)


        # Store the root NodePath for convenience
        root = self.environment.getRoot()
        root.reparentTo(render)
        root.setSz(100)

        # Generate it.
        self.environment.generate()
        root.setCollideMask(BitMask32.allOn())

        '''push_col_node = self.player_node.attachNewNode(CollisionNode('push_col_node'))
        push_col_node.node().addSolid(CollisionSphere(0, 0, 0, 1))
        push_col_node.set_pos(0, 0, 1.15)
        pusher = CollisionHandlerPusher()
        pusher.addCollider(push_col_node, self.player_node)
        self.cTrav.addCollider(push_col_node, pusher)'''

        lift_col_node = self.player_node.attachNewNode(CollisionNode('lift_col_node'))
        lift_col_node.node().addSolid(CollisionRay(0, 0, 1, 0, 0, -1))
        lifter = CollisionHandlerGravity()
        lifter.addCollider(lift_col_node, self.player_node)
        self.cTrav.addCollider(lift_col_node, lifter)

        self.task_mgr.add(self.mouse_look_task, "mouse_look_task")
        self.task_mgr.add(self.player_movement_task, "player_movement_task")

        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)

        self.accept("aspectRatioChanged", self.set_center)
        self.accept("escape", sys.exit)

        dr = self.camNode.getDisplayRegion(0)
        dr.setCamera(self.player_camera)


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
            self.player_actor.set_h(180)
            self.player_camera.set_p(self.rot_v)
        self.win.movePointer(0, *self.center)
        return Task.cont

    def player_movement_task(self, _task):
        velocity = Vec3(0, 0, 0)
        speed = 5
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("w")):
            velocity.y = speed
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("s")):
            velocity.y = -speed
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("d")):
            velocity.x = speed
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("a")):
            velocity.x = -speed
        if self.mouseWatcherNode.is_button_down(KeyboardButton.space()):
            velocity.z = 0.5
        self.player_node.set_pos(self.player_node, *velocity)
        #print(self.player_node.getPos())
        return Task.cont

game = Game()
game.run()
