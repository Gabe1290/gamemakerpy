# runner.py
import json
import base64
import sys
import pygame

with open("gamemaker_03.pgm.json", "r") as f:
    project = json.load(f)

WIDTH = project["levels"][0]["width"]
HEIGHT = project["levels"][0]["height"]
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
clock = pygame.time.Clock()

def load_image(sprite):
    img_bytes = base64.b64decode(sprite["img_bytes"]) if sprite["img_bytes"] else None
    if img_bytes:
        import io
        return pygame.image.load(io.BytesIO(img_bytes))
    return pygame.Surface((40,40))

sprites = [load_image(s) for s in project["sprites"]]
level = project["levels"][0]
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    screen.fill((255,255,255))
    # draw sprites at their positions
    for inst in level["instances"]:
        obj = project["objects"][inst["object_index"]]
        if obj["sprite_index"] is not None:
            screen.blit(sprites[obj["sprite_index"]], (inst["x"], inst["y"]))
    pygame.display.flip()
    clock.tick(60)
pygame.quit()
