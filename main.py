import math
import sys

from direct.actor.Actor import Actor
from direct.fsm.FSM import FSM
from direct.gui import DirectGuiGlobals
from direct.gui.DirectButton import DirectButton
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.ShowBase import ShowBase
from direct.showbase.ShowBaseGlobal import globalClock
from direct.task import Task


from panda3d.core import *

loadPrcFileData("", "win-size 1200 720")

ground_mask = BitMask32(0b10)
wall_mask = BitMask32(0b100)
enemy_mask = BitMask32(0b1000)
player_mask = BitMask32(0b100000)
atmosphere_col = 0.7529, 0.6196, 0.3921


class App(ShowBase):
    def __init__(self):
        super().__init__()
        self.set_background_color(*atmosphere_col)
        fsm = AppStateFSM(self)
        fsm.request("MainMenu")


class Player:
    def __init__(self, node, cTrav, base, fsm):
        self.node = node
        self.node.setTag("player", "1")
        self.base = base
        self.fsm = fsm
        self.cam = Camera("player_cam")
        self.camera = self.node.attachNewNode(self.cam)
        self.camera.set_pos(0, 0.35, 1.75)

        self.fall_speed = -1
        self.rot_h = self.rot_v = 0

        self.actor = Actor("assets/models/player.bam")
        self.actor.reparent_to(self.node)
        self.node.set_pos(0, 0, 1)
        # self.actor.loop("Idle")

        self.node.setCollideMask(player_mask)
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
        self.node.set_pos(-8, -8, 1)

        self.hp = 100
        self.hp_bar = HealthBar()
        self.hp_bar.reparent_to(self.base.aspect2d)
        self.hp_bar.setScale(1, 1, 0.5)
        self.hp_bar.setPos(0, 0, -0.75)

    def take_damage(self, damage):
        self.hp -= damage
        self.hp_bar.setHealth(self.hp/100)
        if self.hp <= 0:
            self.fsm.request("DeadScreen")


class Alien:
    def __init__(self, node, initial_pos, player, loader, render, task_mgr, cTrav, enemy_bullet_hit_queue):
        self.node = node
        self.player = player
        self.loader = loader
        self.render = render
        self.task_mgr = task_mgr
        self.cTrav = cTrav
        self.enemy_bullet_hit_queue = enemy_bullet_hit_queue
        self.actor = Actor("assets/models/alien.bam")
        self.actor.reparent_to(self.node)
        self.actor.setScale(0.4, 0.5, 0.5)
        self.actor.set_h(180)
        self.actor.setCollideMask(BitMask32.allOn())
        self.initial_pos = initial_pos
        self.node.set_pos(*initial_pos)
        self.actor.loop("CharacterArmature|Shoot")
        self.hp = 100
        self.hp_bar = HealthBar()
        self.hp_bar.reparent_to(self.node)
        self.hp_bar.setBillboardPointEye(-10, fixed_depth=True)
        self.hp_bar.setScale(0.5)
        self.hp_bar.setPos(0, 0, 0.5)

    def take_damage(self, damage):
        if self.hp <= 0:
            return False
        self.hp -= damage
        self.hp_bar.setHealth(self.hp/100)
        if self.hp <= 0:
            return True
        return False

    def update_task(self, task):
        self.node.lookAt(self.player.node)
        bullet = NodePath("bullet")
        bullet.reparent_to(self.render)
        m = self.loader.load_model("assets/models/ball.bam")
        m.setScale(0.05)
        m.reparent_to(bullet)
        bullet.set_pos(self.node.get_pos())
        bullet.lookAt(self.player.node.get_pos() + Vec3(0, 0, 0.1))

        bullet_col_node = CollisionNode("bullet_col_node")
        bullet_col_node_path = bullet.attachNewNode(bullet_col_node)
        bullet_cs = CollisionSphere(0, 0, 0, 0.01)
        bullet_col_node_path.show()
        bullet_col_node_path.setPythonTag("bullet", bullet)

        bullet_col_node.addSolid(bullet_cs)
        bullet_col_node.setFromCollideMask(ground_mask | player_mask)
        bullet_col_node.setIntoCollideMask(0)
        self.cTrav.addCollider(bullet_col_node_path, self.enemy_bullet_hit_queue)

        def cb(task, bullet=bullet):
            bullet.set_fluid_pos(bullet, 0, 0.5, 0)

            d = bullet.getPythonTag("dist") or 0
            if d > 50:
                bullet.remove_node()
                return task.done
            bullet.setPythonTag("dist", d + 0.5)
            return task.cont
        self.task_mgr.add(cb, f"bullet{id(bullet)}_update")
        return task.again


class AppStateFSM(FSM):
    def __init__(self, base):
        super().__init__("AppStateFSM")
        self.base = base

    def enterMainMenu(self):
        self.menu = MainMenu(self)

    def exitMainMenu(self):
        self.menu.destroy()

    def enterHowToPlay(self):
        self.how_to_play = HowToPlay(self)

    def exitHowToPlay(self):
        self.how_to_play.destroy()

    def enterGame(self):
        self.game = Game(self, self.base)

    def exitGame(self):
        self.game.destroy()

    def enterCredits(self):
        self.credits = Credits(self)

    def exitCredits(self):
        self.credits.destroy()

    def enterDeadScreen(self):
        self.dead_screen = DeadScreen(self)

    def exitDeadScreen(self):
        self.dead_screen.destroy()


class MainMenu:
    def __init__(self, fsm):
        self.im = OnscreenImage("assets/logo.png", pos=(0, 0, 0.6), scale=(0.8, 1, 0.4))
        self.title = OnscreenImage("assets/title.png", pos=(0, 0, 0.1), scale=(0.8, 1, 0.12))
        self.title.setTransparency(TransparencyAttrib.MAlpha)
        self.buttons = [
            make_button("NEW GAME", lambda: fsm.request("Game"), (0, 0, -0.2)),
            make_button("HOW TO PLAY", lambda: fsm.request("HowToPlay"), (0, 0, -0.39)),
            make_button("CREDITS", lambda: fsm.request("Credits"), (0, 0, -0.57)),
            make_button("QUIT", sys.exit, (0, 0, -0.75)),
        ]

    def destroy(self):
        self.im.destroy()
        self.title.destroy()
        for button in self.buttons:
            button.destroy()


class HowToPlay:
    def __init__(self, fsm):
        self.text = OnscreenText("Lorem Ipsum", fg=(1, 1, 1, 1), pos=(0, 0.7), wordwrap=35)
        self.back_button = make_button("BACK", lambda: fsm.request("MainMenu"), (0, 0, -0.75))

    def destroy(self):
        self.text.destroy()
        self.back_button.destroy()


class Credits:
    def __init__(self, fsm):
        self.text = OnscreenText("Generic Placeholder", fg=(1, 1, 1, 1), pos=(0, 0.7), wordwrap=35)
        # TODO:
        # Mini Fantasy Tank by Maxwell Planck [CC-BY], via Poly Pizza
        # Robot Enemy Legs by Quaternius
        self.back_button = make_button("BACK", lambda: fsm.request("MainMenu"), (0, 0, -0.75))

    def destroy(self):
        self.text.destroy()
        self.back_button.destroy()


class DeadScreen:
    def __init__(self, fsm):
        self.text = OnscreenText("YOU DIED!", fg=(1, 1, 1, 1), pos=(0, 0.4))
        self.menu_button = make_button("BACK TO MENU", lambda: fsm.request("MainMenu"), (0, 0, -0.6))
        self.again_button = make_button("PLAY AGAIN", lambda: fsm.request("Game"), (0, 0, -0.8))

    def destroy(self):
        self.text.destroy()
        self.menu_button.destroy()
        self.again_button.destroy()


class Game:
    def __init__(self, fsm, base):
        self.base = base
        self.fsm = fsm

        self.center = None
        self.set_center()

        self.mouse_sensitivity = 20

        self.environment = base.loader.load_model("assets/models/terrain.bam")
        self.environment.reparent_to(base.render)
        self.environment.setCollideMask(ground_mask)

        self.boundary_mountains = base.loader.load_model("assets/models/mountain.bam")
        self.boundary_mountains.reparent_to(base.render)
        self.boundary_mountains.set_pos(0, 0, -0.5)
        self.boundary_mountains.setCollideMask(wall_mask)

        expfog = Fog("scene-wide-fog")
        expfog.setColor(*atmosphere_col)
        expfog.setExpDensity(0.004)
        base.render.setFog(expfog)

        ambientLight = AmbientLight("ambientLight")
        ambientLight.setColor(Vec4(0.6, 0.6, 0.6, 1))
        directionalLight = DirectionalLight("directionalLight")
        directionalLight.setDirection(Vec3(0, -10, -10))
        directionalLight.setColor(Vec4(1, 1, 1, 1))
        directionalLight.setSpecularColor(Vec4(1, 1, 1, 1))
        base.render.setLight(base.render.attachNewNode(ambientLight))
        base.render.setLight(base.render.attachNewNode(directionalLight))

        base.cTrav = CollisionTraverser()
        base.cTrav.setRespectPrevTransform(True)

        self.rover = base.loader.load_model("assets/models/rover.bam")
        self.rover.reparent_to(base.render)
        self.rover.set_pos(2, 3, 0.5)
        self.rover.set_scale(0.3)
        self.rover.setCollideMask(wall_mask)

        player_node = NodePath("player_node")
        player_node.reparent_to(base.render)
        self.player = Player(player_node, base.cTrav, base, self.fsm)
        gun_node = NodePath("gun_node")
        self.gun = Gun(gun_node, self.base.loader.loadModel("assets/models/gun.gltf"))
        self.gun.node.set_h(90)
        self.gun.node.set_r(-5)
        self.gun.node.set_pos(Vec3(0.3, 2, -0.4))
        self.gun.node.reparent_to(self.player.camera)
        self.enemy_bullet_hit_queue = CollisionHandlerQueue()
        alien_centre = Vec3(2, 3, 1)
        alien_radius = 4
        self.num_aliens = 5
        for i in range(self.num_aliens):
            alien = Alien(
                NodePath(f"alien{i}_node"),
                alien_centre + Vec3(alien_radius * math.cos(2 * math.pi / self.num_aliens * i), alien_radius * math.sin(2 * math.pi / self.num_aliens * i), 0),
                self.player,
                base.loader,
                base.render,
                base.task_mgr,
                base.cTrav,
                self.enemy_bullet_hit_queue
            )
            alien.node.reparent_to(base.render)
            alien.node.setCollideMask(enemy_mask)
            alien.node.setPythonTag("alien", alien)
            base.task_mgr.doMethodLater(5, alien.update_task, f"alien{id(alien)}_update")

        self.aliens_killed = 0
        self.aliens_killed_bar = HealthBar()
        self.aliens_killed_bar.setHealth(0)
        self.aliens_killed_bar.reparent_to(base.aspect2d)
        self.aliens_killed_bar.setPos(1.1, 0, 0.9)
        self.aliens_killed_bar.setScale(1, 0, 0.5)
        self.ak_text_n = TextNode("aliens_killed_text_node")
        self.ak_text_n.set_text(f"{self.aliens_killed}/{self.num_aliens}")
        self.ak_text_np = self.aliens_killed_bar.attachNewNode(self.ak_text_n)
        self.ak_text_np.set_scale(0.1, 1, 0.2)
        self.ak_text_np.set_pos((-0.1, 0, -0.05))
        self.alien_im = OnscreenImage("assets/alien.png", pos=(-0.4, 0, 0))
        self.alien_im.setScale(0.1)
        self.alien_im.setTransparency(TransparencyAttrib.MAlpha)
        self.alien_im.reparent_to(self.aliens_killed_bar)

        self.crosshair = OnscreenImage(image="assets/textures/cross.png", pos=(0, 0, 0))
        self.crosshair.setTransparency(TransparencyAttrib.MAlpha)
        self.crosshair.setScale(0.1)

        base.task_mgr.add(self.mouse_look_task, "mouse_look_task")
        base.task_mgr.add(self.player_movement_task, "player_movement_task")
        base.task_mgr.add(self.check_enemy_bullets_task, "check_enemy_bullets_task")
        base.task_mgr.doMethodLater(0.25, self.fire_bullet_task, "fire_bullet_task")

        self.props = WindowProperties()
        self.props.setCursorHidden(True)
        base.win.requestProperties(self.props)

        base.accept("aspectRatioChanged", self.set_center)
        base.accept("escape", lambda: self.fsm.request("MainMenu"))
        dr = base.camNode.getDisplayRegion(0)
        dr.setCamera(self.player.camera)

    def set_center(self):
        self.center = (self.base.win.getXSize() // 2, self.base.win.getYSize() // 2)

    def mouse_look_task(self, _task):
        if self.base.mouseWatcherNode.hasMouse():
            mx = self.base.mouseWatcherNode.getMouseX()
            my = self.base.mouseWatcherNode.getMouseY()
            self.player.rot_h += -1 * self.mouse_sensitivity * mx
            self.player.rot_v += self.mouse_sensitivity * my
            self.rot_v = min(90, max(-90, self.player.rot_v))
            self.player.node.set_hpr(self.player.rot_h, 0, 0)
            self.player.camera.set_p(self.rot_v)
        self.base.win.movePointer(0, *self.center)
        return Task.cont

    def player_movement_task(self, _task):
        velocity = Vec3(0, 0, 0)
        dt = globalClock.getDt()
        speed = Vec3(20, 15, 10)  # front, back, sideways
        if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("w")):
            velocity.y = speed.x * dt
        if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("s")):
            velocity.y = -speed.y * dt
        if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("d")):
            velocity.x = speed.z * dt
        if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("a")):
            velocity.x = -speed.z * dt
        if (
            self.base.mouseWatcherNode.is_button_down(KeyboardButton.space())
            and self.player.lifter.isOnGround()
        ):
            self.player.lifter.set_velocity(math.sqrt(2 * 0.3))
        self.player.node.set_pos(self.player.node, *velocity)
        return Task.cont

    def fire_bullet_task(self, task):
        if not self.base.mouseWatcherNode.is_button_down(MouseButton.one()):
            return task.cont
        for entry in self.player.gun_queue.entries:
            alien = entry.getIntoNodePath().getNetPythonTag("alien")
            if not alien:
                continue

            def cb(alien=alien):
                alien.node.remove_node()
                self.base.task_mgr.remove(f"alien{id(alien)}_update")

            if alien.take_damage(5):
                self.aliens_killed += 1
                self.aliens_killed_bar.setHealth(self.aliens_killed/self.num_aliens)
                self.ak_text_n.set_text(f"{self.aliens_killed}/{self.num_aliens}")
                alien.actor.play("CharacterArmature|Death")
                self.base.task_mgr.doMethodLater(2, cb, "dead_alien_remove", extraArgs=[])
        return task.again

    def check_enemy_bullets_task(self, task):
        for entry in self.enemy_bullet_hit_queue.entries:
            bullet = entry.getFromNodePath().getPythonTag("bullet")
            bullet.remove_node()
            self.base.task_mgr.remove(f"bullet{id(bullet)}_update")
            if entry.getIntoNodePath().findNetTag("player"):
                self.player.take_damage(1)
        return task.cont

    def destroy(self):
        self.player.camera.node().getDisplayRegion(0).setCamera(self.base.cam)
        self.base.render.node().removeAllChildren()
        self.player.hp_bar.remove_node()
        self.aliens_killed_bar.remove_node()
        self.base.task_mgr.remove("mouse_look_task")
        self.base.task_mgr.remove("player_movement_task")
        self.base.task_mgr.remove("check_enemy_bullets_task")
        self.base.task_mgr.remove("fire_bullet_task")
        self.base.task_mgr.removeTasksMatching("bullet*")
        self.base.task_mgr.removeTasksMatching("alien*")
        self.crosshair.destroy()
        self.props.setCursorHidden(False)
        self.base.win.requestProperties(self.props)


def make_button(text, callback, pos):
    return DirectButton(
        text=text,
        command=callback,
        pos=pos,
        scale=(0.12, 1, 0.12),
        text_scale=(0.9, 0.9),
        text_bg=(0, 0.085, 0.125, 1),
        text_fg=(0, 0.7, 1, 1),
        relief=DirectGuiGlobals.GROOVE,
        frameColor=(0, 0.35, 0.5, 1),
        text_shadow=(0, 0.0425, 0.0625, 1),
    )


class Gun:
    def __init__(self, node, model):
        self.node = node
        self.model = model
        self.model.reparent_to(self.node)


class HealthBar(NodePath):
    def __init__(self):
        NodePath.__init__(self, 'healthbar')

        cmfg = CardMaker('fg')
        cmfg.setFrame(0, 1, -0.1, 0.1)
        self.fg = self.attachNewNode(cmfg.generate())
        self.fg.setPos(-0.5, 0, 0)

        cmbg = CardMaker('bg')
        cmbg.setFrame(-1, 0, -0.1, 0.1)
        self.bg = self.attachNewNode(cmbg.generate())
        self.bg.setPos(0.5, 0, 0)

        self.fg.setColor(0, 1, 0, 1)
        self.bg.setColor(0.5, 0.5, 0.5, 1)

        self.setHealth(1)

    def setHealth(self, value):
        self.fg.setScale(value, 1, 1)
        self.bg.setScale(1.0 - value, 1, 1)


app = App()
app.run()
