import datetime
import math
import sys
import random
from pathlib import Path

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

ground_mask = BitMask32.bit(1)
wall_mask = BitMask32.bit(2)
enemy_mask = BitMask32.bit(3)
player_mask = BitMask32.bit(4)
rover_mask = BitMask32.bit(5)
spaceship_mask = BitMask32.bit(6)
atmosphere_col = 0.7529, 0.6196, 0.3921


class App(ShowBase):
    def __init__(self):
        super().__init__()
        props = WindowProperties()
        props.set_title("Martian Madness")
        props.icon_filename = "assets/logo.ico"
        self.win.requestProperties(props)
        self.music = self.loader.loadSfx("assets/sfx/music.wav")
        self.music.setVolume(0.5)
        self.music.setLoop(True)
        self.music.play()
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
        self.camera.set_pos(0, 0.0, 1.75)

        self.jump_velocity = Vec3(-1, -1, -1)
        self.rot_h = self.rot_v = 0
        self.grounded = True

        self.actor = Actor("assets/models/player.bam")
        self.actor.reparent_to(self.node)
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

        # lift_col_node = self.node.attachNewNode(CollisionNode("lift_col_node"))
        # lift_col_node.node().addSolid(CollisionRay(0, 0, 1, 0, 0, -1))
        # lift_col_node.node().setFromCollideMask(ground_mask)
        # lift_col_node.node().setIntoCollideMask(0)
        # self.lifter = CollisionHandlerGravity()
        # self.lifter.set_gravity(0.5)
        # self.lifter.addCollider(lift_col_node, self.node)
        # cTrav.addCollider(lift_col_node, self.lifter)

        gun_ray_node = CollisionNode("gun_ray_node")
        gun_ray_node_path = self.camera.attachNewNode(gun_ray_node)
        gun_ray = CollisionRay(0, 1, 1, 0, 1, 0)
        gun_ray_node.addSolid(gun_ray)
        gun_ray_node.setFromCollideMask(enemy_mask | ground_mask | wall_mask)
        gun_ray_node.setIntoCollideMask(0)
        self.gun_queue = CollisionHandlerQueue()
        cTrav.addCollider(gun_ray_node_path, self.gun_queue)

        vehicle_pointer_ray_node = CollisionNode("vehicle_pointer_ray_node")
        vehicle_pointer_ray_node_path = self.camera.attachNewNode(
            vehicle_pointer_ray_node
        )
        rover_pointer_ray = CollisionRay(0, 1, 1, 0, 1, 0)
        vehicle_pointer_ray_node.addSolid(rover_pointer_ray)
        vehicle_pointer_ray_node.setFromCollideMask(rover_mask | spaceship_mask)
        vehicle_pointer_ray_node.setIntoCollideMask(0)
        handler = CollisionHandlerEvent()
        handler.addInPattern("vehicle_enter")
        handler.addOutPattern("vehicle_exit")
        cTrav.addCollider(vehicle_pointer_ray_node_path, handler)

        self.node.set_scale(self.node, 0.1)
        self.node.set_pos(-8, -8, 1)

        self.hp = 100
        self.hp_bar = HealthBar()
        self.hp_bar.reparent_to(self.base.aspect2d)
        self.hp_bar.setScale(1, 1, 0.5)
        self.hp_bar.setPos(0, 0, -0.75)

    def take_damage(self, damage):
        self.hp -= damage
        self.hp_bar.setHealth(self.hp / 100)
        if self.hp <= 0:
            self.fsm.request("DeadScreen")


class Alien:
    def __init__(
        self,
        node,
        initial_pos,
        player,
        loader,
        render,
        task_mgr,
        cTrav,
        enemy_bullet_hit_queue,
    ):
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
        # self.hp_bar = HealthBar()
        # self.hp_bar.reparent_to(self.node)
        # self.hp_bar.setBillboardPointEye(-10, fixed_depth=True)
        # self.hp_bar.setScale(0.5)
        # self.hp_bar.setPos(0, 0, 0.5)

    def take_damage(self, damage):
        if self.hp <= 0:
            return False
        self.hp -= damage
        # self.hp_bar.setHealth(self.hp / 100)
        if self.hp <= 0:
            return True
        return False

    def update_task(self, task):
        if (self.node.get_pos() - self.player.node.get_pos()).length() > 20:
            return task.cont
        self.node.lookAt(self.player.node)
        bullet = NodePath("bullet")
        bullet.reparent_to(self.render)
        m = self.loader.load_model("assets/models/ball.bam")
        m.setScale(0.05)
        m.reparent_to(bullet)
        bullet.set_pos(self.node, 0, 0, 0.5)
        bullet.lookAt(self.player.node.get_pos() + Vec3(0, 0, 0.1))

        bullet_col_node = CollisionNode("bullet_col_node")
        bullet_col_node_path = bullet.attachNewNode(bullet_col_node)
        bullet_cs = CollisionSphere(0, 0, 0, 0.01)
        bullet_col_node_path.show()
        bullet_col_node_path.setPythonTag("bullet", bullet)

        bullet_col_node.addSolid(bullet_cs)
        bullet_col_node.setFromCollideMask(ground_mask | player_mask | wall_mask)
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


class WinScreen:
    def __init__(self, fsm, time_elapsed):
        self.text = OnscreenText(f"YOU WON!\n\nTime: {time_elapsed}", fg=(1, 1, 1, 1), pos=(0, 0.4))
        self.menu_button = make_button(
            "BACK TO MENU", lambda: fsm.request("MainMenu"), (0, 0, -0.6)
        )
        self.again_button = make_button(
            "PLAY AGAIN", lambda: fsm.request("Level1"), (0, 0, -0.8)
        )

    def destroy(self):
        self.text.destroy()
        self.menu_button.destroy()
        self.again_button.destroy()


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

    def enterLevel1(self):
        self.level1 = Level1(self, self.base)

    def exitLevel1(self):
        self.level1.destroy()

    def enterLevel2(self):
        self.level2 = Level2(self, self.base)

    def exitLevel2(self):
        self.level2.destroy()

    def enterCredits(self):
        self.credits = Credits(self)

    def exitCredits(self):
        self.credits.destroy()

    def enterDeadScreen(self):
        self.dead_screen = DeadScreen(self)

    def exitDeadScreen(self):
        self.dead_screen.destroy()

    def enterWinScreen(self, time_elapsed):
        self.win_screen = WinScreen(self, time_elapsed)

    def exitWinScreen(self):
        self.win_screen.destroy()


class MainMenu:
    def __init__(self, fsm):
        self.im = OnscreenImage("assets/logo.png", pos=(0, 0, 0.6), scale=(0.8, 1, 0.4))
        self.im.setTransparency(TransparencyAttrib.MAlpha)
        self.title = OnscreenImage(
            "assets/title.png", pos=(0, 0, 0.1), scale=(0.8, 1, 0.12)
        )
        self.title.setTransparency(TransparencyAttrib.MAlpha)
        self.buttons = [
            make_button("NEW GAME", lambda: fsm.request("Level1"), (0, 0, -0.2)),
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
        self.text = OnscreenText(
            Path("assets/how_to_play.txt").read_text(),
            fg=(1, 1, 1, 1),
            pos=(0, 0.7),
            wordwrap=35,
        )
        self.back_button = make_button(
            "BACK", lambda: fsm.request("MainMenu"), (0, 0, -0.75)
        )

    def destroy(self):
        self.text.destroy()
        self.back_button.destroy()


class Credits:
    def __init__(self, fsm):
        self.text = OnscreenText(
            Path("assets/credits.txt").read_text(),
            fg=(1, 1, 1, 1),
            pos=(0, 0.7),
            wordwrap=35,
        )
        self.back_button = make_button(
            "BACK", lambda: fsm.request("MainMenu"), (0, 0, -0.75)
        )

    def destroy(self):
        self.text.destroy()
        self.back_button.destroy()


class DeadScreen:
    def __init__(self, fsm):
        self.text = OnscreenText("YOU DIED!", fg=(1, 1, 1, 1), pos=(0, 0.4))
        self.menu_button = make_button(
            "BACK TO MENU", lambda: fsm.request("MainMenu"), (0, 0, -0.6)
        )
        self.again_button = make_button(
            "PLAY AGAIN", lambda: fsm.request("Level1"), (0, 0, -0.8)
        )

    def destroy(self):
        self.text.destroy()
        self.menu_button.destroy()
        self.again_button.destroy()


class LevelBase:
    def __init__(self, fsm, base):
        self.base = base
        self.fsm = fsm

        self.center = None
        self.set_center()

        self.mouse_sensitivity = 20

        expfog = Fog("scene-wide-fog")
        expfog.setColor(*atmosphere_col)
        expfog.setExpDensity(0.002)
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

        player_node = NodePath("player_node")
        player_node.reparent_to(base.render)
        self.player = Player(player_node, base.cTrav, base, self.fsm)
        self.player.node.set_pos(23, 50, 0)
        gun_node = NodePath("gun_node")
        self.gun = Gun(gun_node, self.base.loader.loadModel("assets/models/gun.gltf"))
        self.gun.node.set_h(90)
        self.gun.node.set_r(-5)
        self.gun.node.set_pos(Vec3(0.3, 2, -0.4))
        self.gun.node.reparent_to(self.player.camera)
        self.enemy_bullet_hit_queue = CollisionHandlerQueue()

        self.terrain = GeoMipTerrain("terrain")
        # self.terrain.setBruteforce(True)
        self.terrain.setHeightfield("assets/textures/Heightmap.png")
        img = PNMImage(257, 257, 3)
        img.fillVal(163, 69, 41)
        self.terrain.set_color_map(img)
        self.terrain.set_focal_point(self.player.camera)
        self.terrain.generate()
        self.terrain_mesh = self.terrain.get_root()
        self.terrain_mesh.setSz(20)
        self.terrain_mesh.reparentTo(base.render)
        self.terrain_mesh.setCollideMask(ground_mask)

        self.num_aliens = None

        self.aliens_killed = 0
        self.aliens_killed_bar = HealthBar()
        self.aliens_killed_bar.setHealth(0)
        self.aliens_killed_bar.reparent_to(base.aspect2d)
        self.aliens_killed_bar.setPos(1.1, 0, 0.9)
        self.aliens_killed_bar.setScale(1, 0, 0.5)
        self.ak_text_n = TextNode("aliens_killed_text_node")
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

        self.gun_sfx = self.base.loader.loadSfx("assets/sfx/gun.mp3")
        self.hurt_sfx = self.base.loader.loadSfx("assets/sfx/hurt.mp3")

        base.task_mgr.add(self.mouse_look_task, "mouse_look_task")
        base.task_mgr.add(self.player_movement_task, "player_movement_task")
        base.task_mgr.add(self.check_enemy_bullets_task, "check_enemy_bullets_task")
        base.task_mgr.add(self.update_terrain_task, "update_terrain_task")
        base.task_mgr.add(self.update_timer_task, "update_timer_task")
        base.task_mgr.doMethodLater(0.25, self.fire_bullet_task, "fire_bullet_task")

        self.minimap_pos = Vec3(-1.4, 0, 0.7)
        self.minimap = OnscreenImage(
            image="assets/textures/minimap.png",
            scale=(0.25, 1, 0.25),
            pos=self.minimap_pos,
        )
        a = self.minimap.getTightBounds()
        self.minimap_rad = (a[1].x - a[0].x) / 2
        self.minimap.setTransparency(TransparencyAttrib.MAlpha)

        self.pmm_image = OnscreenImage(
            image="assets/textures/playerhead.png",
            pos=self.minimap_pos,
            scale=(0.015, 1, 0.015),
        )
        self.pmm_image.setTransparency(TransparencyAttrib.MAlpha)

        self.timer = OnscreenText("00:00", mayChange=True, pos=(0, -0.85))
        self.timer.reparent_to(self.base.aspect2d)
        self.start_time = datetime.datetime.now()
        self.time_elapsed = None

        self.props = WindowProperties()
        self.props.setCursorHidden(True)
        base.win.requestProperties(self.props)

        base.accept("aspectRatioChanged", self.set_center)
        base.accept("escape", lambda: self.fsm.request("MainMenu"))

        dr = base.camNode.getDisplayRegion(0)
        dr.setCamera(self.player.camera)

    def set_center(self):
        self.center = (self.base.win.getXSize() // 2, self.base.win.getYSize() // 2)

    def update_terrain_task(self, _task):
        self.terrain.update()
        return Task.cont

    def mouse_look_task(self, _task):
        if self.base.mouseWatcherNode.hasMouse():
            mx = self.base.mouseWatcherNode.getMouseX()
            my = self.base.mouseWatcherNode.getMouseY()
            self.player.rot_h += -1 * self.mouse_sensitivity * mx
            self.player.rot_v += self.mouse_sensitivity * my
            self.rot_v = min(90, max(-90, self.player.rot_v))
            self.player.node.set_hpr(self.player.rot_h, 0, 0)
            self.player.camera.set_p(self.rot_v)
            self.pmm_image.set_r(-self.player.rot_h)
        self.base.win.movePointer(0, *self.center)
        return Task.cont

    def player_movement_task(self, _task):
        velocity = Vec3(0, 0, 0)
        dt = globalClock.getDt()
        speed = Vec3(100, 40, 30)  # front, back, sideways
        x, y, _z = self.player.node.get_pos()
        self.player.node.setX(min(max(1, x), 255))
        self.player.node.setY(min(max(1, y), 255))
        terrain_height = (
            self.terrain.get_elevation(x, y) * self.terrain_mesh.get_sz() + 2
        )
        if self.player.grounded:
            if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("w")):
                velocity.y = speed.x * dt
            if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("s")):
                velocity.y = -speed.y * dt
            if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("d")):
                velocity.x = speed.z * dt
            if self.base.mouseWatcherNode.is_button_down(KeyboardButton.ascii_key("a")):
                velocity.x = -speed.z * dt
            if self.base.mouseWatcherNode.is_button_down(KeyboardButton.space()):
                self.player.jump_velocity = Vec3(
                    velocity.x, velocity.y, math.sqrt(20 * -2 * -9.8)
                )
                self.player.grounded = False
        else:
            velocity.x = self.player.jump_velocity.x
            velocity.y = self.player.jump_velocity.y

        self.player.jump_velocity.z += -9.8 * dt
        velocity.z = self.player.jump_velocity.z * dt
        self.player.node.set_pos(self.player.node, *velocity)

        if self.player.node.getZ() <= terrain_height:
            self.player.node.setZ(terrain_height)
            self.player.grounded = True
            self.player.jump_velocity = Vec3(-1, -1, -1)
        return Task.cont

    def fire_bullet_task(self, task):
        if not self.base.mouseWatcherNode.is_button_down(MouseButton.one()):
            return task.cont
        self.gun_sfx.play()
        for entry in self.player.gun_queue.entries:
            alien = entry.getIntoNodePath().getNetPythonTag("alien")
            if not alien:
                continue

            def cb(alien=alien):
                alien.node.remove_node()
                self.base.task_mgr.remove(f"alien{id(alien)}_update")

            if alien.take_damage(5):
                self.aliens_killed += 1
                self.aliens_killed_bar.setHealth(self.aliens_killed / self.num_aliens)
                self.ak_text_n.set_text(f"{self.aliens_killed}/{self.num_aliens}")
                alien.actor.play("CharacterArmature|Death")
                self.base.task_mgr.doMethodLater(
                    2, cb, "dead_alien_remove", extraArgs=[]
                )
        return task.again

    def update_timer_task(self, task):
        delta = datetime.datetime.now() - self.start_time
        minutes, seconds = divmod(round(delta.total_seconds()), 60)
        self.time_elapsed = f"{minutes:>02}:{seconds:>02}"
        self.timer.setText(self.time_elapsed)
        return task.cont

    def check_enemy_bullets_task(self, task):
        for entry in self.enemy_bullet_hit_queue.entries:
            bullet = entry.getFromNodePath().getPythonTag("bullet")
            bullet.remove_node()
            self.base.task_mgr.remove(f"bullet{id(bullet)}_update")
            if entry.getIntoNodePath().findNetTag("player"):
                self.hurt_sfx.play()
                self.player.take_damage(1)
        return task.cont

    def destroy(self):
        self.player.camera.node().getDisplayRegion(0).setCamera(self.base.cam)
        self.base.render.node().removeAllChildren()
        self.base.render.clearLight()
        self.player.hp_bar.remove_node()
        self.aliens_killed_bar.remove_node()
        self.timer.remove_node()
        self.base.task_mgr.remove("mouse_look_task")
        self.base.task_mgr.remove("player_movement_task")
        self.base.task_mgr.remove("check_enemy_bullets_task")
        self.base.task_mgr.remove("fire_bullet_task")
        self.base.task_mgr.remove("draw_aliens_mipmap_task")
        self.base.task_mgr.remove("update_timer_task")
        self.base.task_mgr.removeTasksMatching("bullet*")
        self.base.task_mgr.removeTasksMatching("alien*")
        self.crosshair.destroy()
        self.props.setCursorHidden(False)
        self.base.win.requestProperties(self.props)


class Level1(LevelBase):
    def __init__(self, fsm, base):
        super().__init__(fsm, base)
        self.rover_map_im = OnscreenImage("assets/textures/rover.png", scale=(0.02, 1, 0.02))
        self.rover_map_im.setTransparency(TransparencyAttrib.MAlpha)
        self.rover_map_im.hide()

        self.rover = base.loader.load_model("assets/models/rover.bam")
        self.rover.reparent_to(base.render)
        self.rover.set_pos(
            20, 50, self.terrain.get_elevation(20, 50) * self.terrain_mesh.get_sz()
        )
        self.rover.set_scale(0.3)
        self.rover.setCollideMask(wall_mask | rover_mask)

        self.rover_message = None

        self.num_aliens = 10
        self.aliens = []
        self.imgs = []
        for i in range(self.num_aliens):
            self.imgs.append(
                OnscreenImage(
                    image="assets/textures/enemy.png",
                    scale=(0.02, 1, 0.02),
                )
            )
            self.imgs[i].setTransparency(TransparencyAttrib.MAlpha)
            self.imgs[i].hide()

        for i in range(self.num_aliens):
            x = random.randint(5, 240)
            y = random.randint(5, 240)
            z = self.terrain.get_elevation(x, y) * self.terrain_mesh.get_sz()
            al = NodePath(f"alien{i}_node")
            self.aliens.append(al)
            alien = Alien(
                al,
                Vec3(x, y, z),
                self.player,
                base.loader,
                base.render,
                base.task_mgr,
                base.cTrav,
                self.enemy_bullet_hit_queue,
            )
            alien.node.reparent_to(base.render)
            alien.node.setCollideMask(enemy_mask)
            alien.node.setPythonTag("alien", alien)
            base.task_mgr.doMethodLater(
                0.5, alien.update_task, f"alien{id(alien)}_update"
            )
        base.task_mgr.add(self.draw_aliens_mipmap_task, "draw_aliens_mipmap_task")
        self.ak_text_n.set_text(f"{self.aliens_killed}/{self.num_aliens}")
        base.accept("vehicle_enter", self.rover_enter)
        base.accept("vehicle_exit", self.rover_exit)

    def draw_aliens_mipmap_task(self, task):
        ppos = self.player.node.get_pos()
        for i, alien in enumerate(self.aliens):
            if alien.is_empty():
                self.imgs[i].hide()
            else:
                vec = Vec2(alien.getX(), alien.getY()) - Vec2(ppos.x, ppos.y)
                dist = vec.length()
                if dist <= 50:
                    vn = vec.normalized()
                    self.imgs[i].show()
                    p = (vn * self.minimap_rad) * (dist / 50)
                    self.imgs[i].set_pos(self.minimap_pos + Vec3(p.x, 0, p.y))
                else:
                    self.imgs[i].hide()
        vec = Vec2(self.rover.getX(), self.rover.getY()) - Vec2(ppos.x, ppos.y)
        dist = vec.length()
        if dist <= 50:
            vn = vec.normalized()
            self.rover_map_im.show()
            p = (vn * self.minimap_rad) * (dist / 50)
            self.rover_map_im.set_pos(self.minimap_pos + Vec3(p.x, 0, p.y))
        else:
            self.rover_map_im.hide()
        return task.cont

    def rover_enter(self, _):
        if (self.player.node.get_pos() - self.rover.get_pos()).length() > 5:
            return
        if self.aliens_killed < self.num_aliens:
            self.rover_message = OnscreenText("Kill all aliens to use rover.")
        else:
            self.rover_message = OnscreenText("Press E to use rover.")
            self.base.acceptOnce("e", lambda: self.fsm.request("WinScreen", self.time_elapsed))
        self.rover_message.set_pos(0, 0, -0.3)

    def rover_exit(self, _):
        self.base.ignore("e")
        if self.rover_message:
            self.rover_message.destroy()

    def destroy(self):
        super().destroy()
        if self.rover_message:
            self.rover_message.destroy()
        self.pmm_image.destroy()
        self.minimap.destroy()
        self.rover_map_im.destroy()
        for im in self.imgs:
            im.destroy()


class Level2(LevelBase):
    def __init__(self, fsm, base):
        super().__init__(fsm, base)
        self.player.node.set_pos(8, -8, 1)
        self.spaceship = base.loader.load_model("assets/models/spaceship.bam")
        self.spaceship.reparent_to(base.render)
        self.spaceship.set_pos(
            40, 60, self.terrain.get_elevation(40, 60) * self.terrain_mesh.get_sz()
        )
        self.spaceship.set_scale(0.3)
        self.spaceship.set_h(45)
        self.spaceship.setCollideMask(wall_mask | spaceship_mask | ground_mask)
        self.spaceship_message = None
        base.accept("vehicle_enter", self.spaceship_enter)
        base.accept("vehicle_exit", self.spaceship_exit)

        alien_centre = Vec3(40, 60, 0)
        alien_radius = 4
        self.num_aliens = 15
        for i in range(self.num_aliens):
            x = alien_centre.x + alien_radius * math.cos(
                2 * math.pi / self.num_aliens * i
            )
            y = alien_centre.y + alien_radius * math.sin(
                2 * math.pi / self.num_aliens * i
            )
            z = self.terrain.get_elevation(x, y) * self.terrain_mesh.get_sz()
            alien = Alien(
                NodePath(f"alien{i}_node"),
                Vec3(x, y, z),
                self.player,
                base.loader,
                base.render,
                base.task_mgr,
                base.cTrav,
                self.enemy_bullet_hit_queue,
            )
            alien.node.reparent_to(base.render)
            alien.node.setCollideMask(enemy_mask)
            alien.node.setPythonTag("alien", alien)
            base.task_mgr.doMethodLater(
                2, alien.update_task, f"alien{id(alien)}_update"
            )
        self.ak_text_n.set_text(f"{self.aliens_killed}/{self.num_aliens}")

    def spaceship_enter(self, _):
        if (self.player.node.get_pos() - self.spaceship.get_pos()).length() > 5:
            return
        if self.aliens_killed < self.num_aliens:
            self.spaceship_message = OnscreenText("Kill all aliens to use spaceship.")
        else:
            self.spaceship_message = OnscreenText("Press E to use spaceship.")
            self.base.acceptOnce("e", lambda: self.fsm.request("WinScreen"))
        self.spaceship_message.set_pos(0, 0, -0.3)

    def spaceship_exit(self, _):
        self.base.ignore("e")
        if self.spaceship_message:
            self.spaceship_message.destroy()

    def destroy(self):
        super().destroy()
        if self.spaceship_message:
            self.spaceship_message.destroy()


def make_button(text, callback, pos):
    return DirectButton(
        text=text,
        command=callback,
        pos=pos,
        scale=(0.12, 1, 0.12),
        text_scale=(0.9, 0.9),

        text_bg=(249/255, 161/255, 72/255, 1),
        text_fg=(0, 0, 0, 1),
        relief=DirectGuiGlobals.GROOVE,
        frameColor=(184/255, 64/255, 22/255, 1),
        text_shadow=(0, 0.0425, 0.0625, 1),
    )


class Gun:
    def __init__(self, node, model):
        self.node = node
        self.model = model
        self.model.reparent_to(self.node)


class HealthBar(NodePath):
    def __init__(self):
        NodePath.__init__(self, "healthbar")

        cmfg = CardMaker("fg")
        cmfg.setFrame(0, 1, -0.1, 0.1)
        self.fg = self.attachNewNode(cmfg.generate())
        self.fg.setPos(-0.5, 0, 0)

        cmbg = CardMaker("bg")
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
