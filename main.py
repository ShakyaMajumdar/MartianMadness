import re
import math
import sys

from direct.actor.Actor import Actor
from direct.gui.OnscreenImage import OnscreenImage
from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import *
  
loadPrcFileData('', 'win-size 1200 720')

ground_mask = BitMask32(0b10)
wall_mask = BitMask32(0b100)
enemy_mask = BitMask32(0b1000)


class Game(ShowBase):
    def __init__(self):
        super().__init__()

        self.center = None
        self.set_center()

        self.mouse_sensitivity = 20

        self.rot_v = 0
        self.rot_h = 0

        self.environment = self.loader.load_model("assets/models/terrain.bam")
        self.environment.reparent_to(self.render)
        self.environment.setCollideMask(ground_mask)

        self.spaceSkyBox = self.loader.loadModel("assets/models/skybox.bam")
        self.spaceSkyBox.setScale(100)
        self.spaceSkyBox.setBin("background", 0)
        self.spaceSkyBox.setDepthWrite(0)
        self.spaceSkyBox.setTwoSided(True)
        self.spaceSkyBox.reparent_to(self.render)

        self.light = self.render.attach_new_node(PointLight("light"))
        self.light.set_pos(0, 10, 5)
        self.render.set_light(self.light)
        alight = AmbientLight("alight")
        alnp = self.render.attachNewNode(alight)
        alight.setColor((0.1, 0.1, 0.1, 1))
        self.render.setLight(alnp)

        self.cTrav = CollisionTraverser()

        player_node = NodePath("player_node")
        player_node.reparent_to(self.render)
        self.player = Player(player_node, self.cTrav)

        gun_node = NodePath("gun_node")
        self.gun = Gun(gun_node, self.loader.loadModel("assets/models/gun.gltf"))
        self.gun.node.set_h(90)
        self.gun.node.set_r(-5)
        self.gun.node.set_pos(Vec3(0.3, 2, -0.4))
        self.gun.node.reparent_to(self.player.camera)

        self.aliens = {}
        for i in range(10):
            alien = Alien(NodePath(f"alien{i}_node"), (i * 3 - 15, 10, 1))
            alien.node.reparent_to(self.render)
            alien.node.node().setIntoCollideMask(enemy_mask)
            self.aliens[f"alien{i}_node"] = alien

        crosshair = OnscreenImage(image="assets/textures/cross.png", pos=(0, 0, 0))
        crosshair.setTransparency(TransparencyAttrib.MAlpha)
        crosshair.setScale(0.1)

        self.task_mgr.add(self.mouse_look_task, "mouse_look_task")
        self.task_mgr.add(self.player_movement_task, "player_movement_task")
        self.task_mgr.do_method_later(1, self.update_aliens_task, "update_aliens_task")

        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)

        self.accept("mouse1", self.fire_bullet)
        self.accept("aspectRatioChanged", self.set_center)
        self.accept("escape", sys.exit)

        debug_cam = Camera("debug_cam")
        debug_camera = self.render.attachNewNode(debug_cam)
        debug_camera.set_pos(0, 2, 1)
        debug_camera.lookAt(self.player.node)
        dr = self.camNode.getDisplayRegion(0)
        dr.setCamera(self.player.camera)
        # dr.setActive(0)
        # window = dr.getWindow()
        # dr1 = window.makeDisplayRegion(0, 0.5, 0, 1)
        # dr1.setSort(dr.getSort())
        # dr2 = window.makeDisplayRegion(0.5, 1, 0, 1)
        # dr2.setSort(dr.getSort())
        # dr1.setCamera(self.player_camera)
        # dr2.setCamera(debug_camera)

    def set_center(self):
        self.center = (self.win.getXSize() // 2, self.win.getYSize() // 2)

    def mouse_look_task(self, _task):
        if self.mouseWatcherNode.hasMouse():
            mx = self.mouseWatcherNode.getMouseX()
            my = self.mouseWatcherNode.getMouseY()
            self.rot_h += -1 * self.mouse_sensitivity * mx
            self.rot_v += self.mouse_sensitivity * my
            self.rot_v = min(90, max(-90, self.rot_v))
            self.player.node.set_hpr(self.rot_h, 0, 0)
            self.player.actor.set_h(180)
            self.player.camera.set_p(self.rot_v)
        self.win.movePointer(0, *self.center)
        return Task.cont

    def player_movement_task(self, _task):
        velocity = Vec3(0, 0, 0)
        dt = globalClock.getDt()
        speed = Vec3(20, 15, 10) # front, back, sideways
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("w")):
            velocity.y = speed.x * dt
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("s")):
            velocity.y = -speed.y * dt
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("d")):
            velocity.x = speed.z * dt
        if self.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("a")):
            velocity.x = -speed.z * dt
        if self.mouseWatcherNode.is_button_down(KeyboardButton.space()):
            if self.player.lifter.isOnGround():
                self.player.lifter.set_velocity(math.sqrt(2 * 0.3))
        self.player.node.set_pos(self.player.node, *velocity)
        return Task.cont

    def fire_bullet(self):

        for entry in self.player.gun_queue.entries:
            alien = self._get_alien_from_hit_entry(entry)
            if not alien:
                continue

            def cb(alien=alien):
                self.aliens.pop(alien.node.name)
                alien.node.remove_node()

            if alien.take_damage(20):
                alien.actor.play("CharacterArmature|Death")
                self.task_mgr.doMethodLater(2, cb, "dead_alien_remove", extraArgs=[])

    def _get_alien_from_hit_entry(self, entry):
        target = entry.getIntoNodePath()
        if not (alien_node_name := re.search(r"alien\d+_node", str(target))):
            return
        alien_node_name = alien_node_name.group(0)
        return self.aliens.get(alien_node_name)

    def update_aliens_task(self, _task):
        for alien in self.aliens.values():
            alien.node.lookAt(self.player.node)
            bullet = NodePath("bullet")
            bullet.reparent_to(self.render)
            m = self.loader.load_model("assets/models/ball.bam")
            m.setScale(0.05)
            m.reparent_to(bullet)
            bullet.set_pos(alien.node.get_pos())
            bullet.lookAt(self.player.node)

            def cb(task, bullet=bullet):
                bullet.set_pos(bullet, 0, 0.6, 0)
                return task.cont

            self.task_mgr.add(cb, "bullet_update")
            alien.actor.set_h(180)

        return Task.again


class Player:
    def __init__(self, node, cTrav):
        self.node = node

        self.cam = Camera("player_cam")
        self.camera = self.node.attachNewNode(self.cam)
        self.camera.set_pos(0, 0.35, 1.75)

        self.fall_speed = -1

        self.actor = Actor("assets/models/player.bam")
        self.actor.reparent_to(self.node)
        self.node.set_pos(0, 0, 1)
        #self.actor.loop("Idle")

        push_col_node = self.node.attachNewNode(CollisionNode("push_col_node"))
        push_col_node.node().addSolid(CollisionSphere(0, 0, 0, 1))
        push_col_node.set_pos(0, 0, 1.5)
        push_col_node.node().setFromCollideMask(wall_mask)
        push_col_node.node().setIntoCollideMask(0)
        self.pusher = CollisionHandlerPusher()
        self.pusher.addCollider(push_col_node, self.node)
        cTrav.addCollider(push_col_node, self.pusher)

        lift_col_node = self.node.attachNewNode(CollisionNode("lift_col_node"))
        lift_col_node.node().addSolid(CollisionRay(0, 0, 1, 0, 0, -1))
        lift_col_node.node().setFromCollideMask(ground_mask)
        lift_col_node.node().setIntoCollideMask(0)
        self.lifter = CollisionHandlerGravity()
        self.lifter.set_gravity(0.5)
        self.lifter.addCollider(lift_col_node, self.node)
        cTrav.addCollider(lift_col_node, self.lifter)

        gun_ray_node = CollisionNode("gun_ray_node")
        gun_ray_node_path = self.camera.attachNewNode(gun_ray_node)
        gun_ray = CollisionRay(0, 1, 1, 0, 1, 0)
        gun_ray_node.addSolid(gun_ray)
        gun_ray_node.setFromCollideMask(enemy_mask)
        gun_ray_node.setIntoCollideMask(0)
        self.gun_queue = CollisionHandlerQueue()
        cTrav.addCollider(gun_ray_node_path, self.gun_queue)
        self.node.set_scale(self.node, 0.1)


class Alien:
    def __init__(self, node, initial_pos):
        self.node = node
        self.actor = Actor("assets/models/alien.bam")
        self.actor.reparent_to(self.node)
        self.actor.setScale(0.4, 0.5, 0.5)
        self.actor.setCollideMask(BitMask32.allOn())
        self.initial_pos = initial_pos
        self.node.set_pos(*initial_pos)
        self.actor.loop("CharacterArmature|Shoot")
        self.hp = 100

    def take_damage(self, damage):
        if self.hp <= 0:
            return False
        self.hp -= damage
        if self.hp <= 0:
            return True
        return False


class Gun:
    def __init__(self, node, model):
        self.node = node
        self.model = model
        self.model.reparent_to(self.node)

game = Game()
game.run()
