import sys

from direct.showbase.ShowBase import ShowBase
from panda3d.core import NodePath


class Game(ShowBase):
    def __init__(self):
        super().__init__()

        self.environment = self.loader.load_model("assets/models/ground.bam")
        self.environment.reparent_to(self.render)

        self.player_node = NodePath("player_node")
        self.player_node.reparent_to(self.render)
        self.camera.reparent_to(self.player_node)
        self.player_node.set_pos(0, 0, 1)

        self.accept("escape", sys.exit)


game = Game()
game.run()
