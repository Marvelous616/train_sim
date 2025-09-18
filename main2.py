import pygame
import sys
import json
import math
from pathlib import Path

# ----------------- Initialization -----------------
pygame.init()
WIDTH, HEIGHT = 1920 , 1080

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Train Simulation")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 20)
BG = (240, 240, 240)

# ----------------- Helpers -----------------
def lerp(a, b, t):
    return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

# ----------------- Load JSON -----------------
graph_path = Path("graph.json")
trains_path = Path("trains.json")
node_styles_path = Path("node_styles.json")

with open(graph_path) as f:
    graph_data = json.load(f)
nodes = graph_data["nodes"]
edges = graph_data["edges"]

with open(trains_path) as f:
    trains_cfg = json.load(f)

with open(node_styles_path) as f:
    node_styles = json.load(f)

# ----------------- Drawing -----------------
def draw_edges(surf):
    for edge in edges:
        a, b = nodes[edge[0]]["pos"], nodes[edge[1]]["pos"]
        pygame.draw.line(surf, (180,180,180), a, b, 6)

def draw_node(surf, name, node):
    style = node_styles.get(node.get("type","default"), {})
    color = tuple(style.get("color", [100,100,255]))
    radius = style.get("radius", 10)
    pygame.draw.circle(surf, color, node["pos"], radius)
    txt = FONT.render(name, True, (0,0,0))
    surf.blit(txt, (node["pos"][0]+radius+2, node["pos"][1]-radius-2))

# ----------------- Train class -----------------
class Train:
    def __init__(self, cfg):
        self.id = cfg.get("id", cfg.get("name", "T?"))
        self.route = cfg.get("route") or cfg.get("path")
        if not self.route:
            raise ValueError(f"Train {self.id} missing 'route' or 'path'")
        for n in self.route:
            if n not in nodes:
                raise ValueError(f"Train {self.id} route references unknown node '{n}'")

        self.max_speed = float(cfg.get("max_speed", 2.0))
        self.length = float(cfg.get("length", 40.0))
        self.color = tuple(cfg.get("color", [200,40,40]))
        self.thickness = int(cfg.get("thickness", cfg.get("width", 14)))

        # build path edges
        self.edge_points, self.edge_lengths = [], []
        for i in range(len(self.route)-1):
            u, v = self.route[i], self.route[i+1]
            a, b = nodes[u]["pos"], nodes[v]["pos"]
            self.edge_points.append((a,b))
            self.edge_lengths.append(dist(a,b))
        self.total_len = sum(self.edge_lengths)
        self.abs_dist = float(cfg.get("start_dist",0.0))

    def step(self, dt=1.0):
        self.abs_dist += self.max_speed * dt
        if self.total_len > 0:
            self.abs_dist %= self.total_len

    def get_pos_at(self, gdist):
        if self.total_len == 0:
            return (0,0)
        g = gdist % self.total_len
        rem = g
        for (a,b), seglen in zip(self.edge_points, self.edge_lengths):
            if rem <= seglen or seglen == 0:
                t = (rem / seglen) if seglen > 0 else 0.0
                return lerp(a,b,t)
            rem -= seglen
        return self.edge_points[-1][1]

    def get_front_pos(self):
        return self.get_pos_at(self.abs_dist)

    def get_back_pos(self):
        return self.get_pos_at(self.abs_dist - self.length)

    def draw(self, surf):
        front = self.abs_dist % self.total_len
        back = front - self.length
        pts = self.polyline_between(back, front)
        if len(pts) >= 2:
            int_pts = [(int(x), int(y)) for x,y in pts]
            pygame.draw.lines(surf, self.color, False, int_pts, self.thickness)
            pygame.draw.circle(surf, self.color, int_pts[0], self.thickness//2)
            pygame.draw.circle(surf, self.color, int_pts[-1], self.thickness//2)
        fx, fy = self.get_front_pos()
        label = FONT.render(str(self.id), True, (0,0,0))
        surf.blit(label, (int(fx)+6, int(fy)-8))

    def polyline_between(self, back_gdist, front_gdist, step_px=4):
        span = front_gdist - back_gdist
        if span < 0:
            span += self.total_len
        samples = max(2, int(math.ceil(span / step_px)))
        pts = []
        for i in range(samples+1):
            t = i / samples
            d = back_gdist + t*span
            pts.append(self.get_pos_at(d))
        return pts

# ----------------- Collision detection -----------------
def detect_collisions(trains, surf):
    for i in range(len(trains)):
        for j in range(i+1, len(trains)):
            p1, p2 = trains[i].get_front_pos(), trains[j].get_front_pos()
            d = dist(p1, p2)
            min_dist = (trains[i].thickness + trains[j].thickness)/2
            if d < min_dist:
                print(f"⚠️ Collision between {trains[i].id} and {trains[j].id} (dist={d:.1f})")
                cx, cy = (p1[0]+p2[0])/2, (p1[1]+p2[1])/2
                pygame.draw.circle(surf, (255,0,0), (int(cx), int(cy)), 20, 4)

# ----------------- Initialize trains -----------------
trains = [Train(cfg) for cfg in trains_cfg]

# ----------------- Main loop -----------------
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    # update trains
    for tr in trains:
        tr.step()

    screen.fill(BG)
    draw_edges(screen)
    for tr in trains:
        tr.draw(screen)
    for name, node in nodes.items():
        draw_node(screen, name, node)
    detect_collisions(trains, screen)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
