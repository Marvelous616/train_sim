import pygame
import sys
import json
import math
from pathlib import Path

# ----------------- Initialization -----------------
pygame.init()
WIDTH, HEIGHT = 1920 , 1080

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Train Simulation | Arrow Keys to Pan | Q/E to Zoom")
clock = pygame.time.Clock()
# A dictionary to hold different font sizes, managed by get_font()
FONTS = {}
BG = (240, 240, 240)

# ----------------- Helpers -----------------
def get_font(size):
    """Gets or creates a font of a specific size, caching it for performance."""
    size = int(size) # Ensure size is an integer for dictionary key
    if size not in FONTS:
        FONTS[size] = pygame.font.SysFont(None, size)
    return FONTS[size]

def lerp(a, b, t):
    return (a[0] + (b[0]-a[0])*t, a[1] + (b[1]-a[1])*t)

def dist(a, b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

# ----------------- Camera Class -----------------
class Camera:
    def __init__(self, x, y, width, height):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.zoom = 1.0

    def apply(self, pos):
        """Transforms world coordinates to screen coordinates."""
        return (pos[0] - self.x) * self.zoom + self.width / 2, \
               (pos[1] - self.y) * self.zoom + self.height / 2

    def apply_scalar(self, scalar):
        """Transforms a world scalar (like radius or thickness) to screen scale."""
        return scalar * self.zoom

    def handle_input(self, keys):
        """Handles keyboard input for panning and zooming."""
        pan_speed = 15 / self.zoom  # Pan faster when zoomed out
        zoom_speed = 1.02

        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.x -= pan_speed
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.x += pan_speed
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            self.y -= pan_speed
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            self.y += pan_speed
        if keys[pygame.K_q]:
            self.zoom *= zoom_speed
        if keys[pygame.K_e]:
            self.zoom /= zoom_speed
        
        self.zoom = max(0.1, min(self.zoom, 5.0)) # Clamp zoom level

# ----------------- Load JSON -----------------
graph_path = Path("graph.json")
trains_path = Path("trains.json")
node_styles_path = Path("node_styles.json")
stations_path = Path("stations.json") 

with open(graph_path) as f:
    graph_data = json.load(f)
nodes = graph_data["nodes"]
edges = graph_data["edges"]

with open(trains_path) as f:
    trains_cfg = json.load(f)

try:
    with open(node_styles_path) as f:
        node_styles = json.load(f)
except FileNotFoundError:
    node_styles = {}

try:
    with open(stations_path) as f: 
        stations_data = json.load(f)
except FileNotFoundError:
    stations_data = []

# ----------------- Drawing (with Camera) -----------------
def draw_edges(surf, camera):
    for edge in edges:
        a, b = camera.apply(nodes[edge[0]]["pos"]), camera.apply(nodes[edge[1]]["pos"])
        width = max(1, int(camera.apply_scalar(6)))
        pygame.draw.line(surf, (180,180,180), a, b, width)

def draw_node(surf, name, node, camera):
    style = node_styles.get(node.get("type","default"), {})
    color = tuple(style.get("color", [100,100,255]))
    
    screen_pos = camera.apply(node["pos"])
    screen_radius = max(2, int(camera.apply_scalar(style.get("radius", 10))))
    
    pygame.draw.circle(surf, color, screen_pos, screen_radius)
    
    # Only draw text if it's large enough to be readable
    if screen_radius > 4:
        font = get_font(camera.apply_scalar(20))
        txt = font.render(name, True, (0,0,0))
        surf.blit(txt, (screen_pos[0]+screen_radius+2, screen_pos[1]-screen_radius-2))

def draw_stations(surf, camera):
    for station in stations_data:
        screen_pos = camera.apply(station["pos"])
        screen_size = (camera.apply_scalar(station["size"][0]), camera.apply_scalar(station["size"][1]))
        
        # Culling: Don't draw stations that are off-screen
        if screen_pos[0] + screen_size[0] < 0 or screen_pos[0] > surf.get_width() or \
           screen_pos[1] + screen_size[1] < 0 or screen_pos[1] > surf.get_height():
            continue

        name = station.get("name", "")
        color = station.get("color", [120, 120, 150])
        opacity = station.get("opacity", 128)
        border_width = max(1, int(camera.apply_scalar(station.get("border_width", 2))))
        font_size = int(camera.apply_scalar(station.get("font_size", 20)))
        font_color = station.get("font_color", [20, 20, 20])
        
        station_surface = pygame.Surface(screen_size, pygame.SRCALPHA)
        station_surface.fill((*color, opacity))
        
        if border_width > 0:
            border_color = [max(0, c-40) for c in color]
            border_opacity = min(255, opacity + 50) 
            pygame.draw.rect(station_surface, (*border_color, border_opacity), station_surface.get_rect(), border_width)
        
        surf.blit(station_surface, screen_pos)
        
        if name and font_size > 8: # Only draw text if large enough
            font = get_font(font_size)
            txt = font.render(name, True, font_color)
            text_rect = txt.get_rect(center=(screen_pos[0] + screen_size[0]/2, screen_pos[1] + screen_size[1]/2))
            surf.blit(txt, text_rect)


# ----------------- Train class (with Camera) -----------------
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
            # Handle case where a train has a route with a single node
            return self.edge_points[0][0] if self.edge_points else (0,0)
        g = gdist % self.total_len
        rem = g
        for (a,b), seglen in zip(self.edge_points, self.edge_lengths):
            if rem <= seglen or seglen == 0:
                t = (rem / seglen) if seglen > 0 else 0.0
                return lerp(a,b,t)
            rem -= seglen
        return self.edge_points[-1][1]

    def draw(self, surf, camera):
        front = self.abs_dist % self.total_len
        back = front - self.length
        pts = self.polyline_between(back, front, camera.zoom)
        
        screen_thickness = max(2, int(camera.apply_scalar(self.thickness)))

        if len(pts) >= 2:
            int_pts = [camera.apply(p) for p in pts]
            pygame.draw.lines(surf, self.color, False, int_pts, screen_thickness)
            pygame.draw.circle(surf, self.color, int_pts[0], screen_thickness//2)
            pygame.draw.circle(surf, self.color, int_pts[-1], screen_thickness//2)
        
        # Draw label, ensuring it's not too small
        if camera.zoom > 0.2:
            fx, fy = camera.apply(self.get_pos_at(self.abs_dist))
            font_size = int(camera.apply_scalar(20))
            if font_size > 8:
                label = get_font(font_size).render(str(self.id), True, (0,0,0))
                surf.blit(label, (int(fx)+6, int(fy)-8))

    def polyline_between(self, back_gdist, front_gdist, zoom, step_px=4):
        # Adjust sampling based on zoom to maintain visual smoothness
        step_dist = step_px / zoom
        span = front_gdist - back_gdist
        if span < 0:
            span += self.total_len
        samples = max(2, int(math.ceil(span / step_dist)))
        pts = []
        for i in range(samples+1):
            t = i / samples
            d = back_gdist + t*span
            pts.append(self.get_pos_at(d))
        return pts

# ----------------- Collision detection (with Camera) -----------------
def detect_collisions(trains, surf, camera):
    for i in range(len(trains)):
        for j in range(i+1, len(trains)):
            p1_world, p2_world = trains[i].get_pos_at(trains[i].abs_dist), trains[j].get_pos_at(trains[j].abs_dist)
            d = dist(p1_world, p2_world)
            min_dist = (trains[i].length + trains[j].length) / 2 # A more robust collision check
            if d < min_dist:
                print(f"⚠️ Collision between {trains[i].id} and {trains[j].id} (dist={d:.1f})")
                cx_world, cy_world = (p1_world[0]+p2_world[0])/2, (p1_world[1]+p2_world[1])/2
                cx_screen, cy_screen = camera.apply((cx_world, cy_world))
                radius = int(camera.apply_scalar(20))
                if radius > 2:
                    pygame.draw.circle(surf, (255,0,0), (int(cx_screen), int(cy_screen)), radius, 4)

# ----------------- Initialize trains and camera -----------------
trains = [Train(cfg) for cfg in trains_cfg]
camera = Camera(WIDTH/2, HEIGHT/2, WIDTH, HEIGHT) # Start camera centered

# ----------------- Main loop -----------------
running = True
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False

    # Handle camera movement
    keys = pygame.key.get_pressed()
    camera.handle_input(keys)

    # update trains
    for tr in trains:
        tr.step()

    # --- Drawing ---
    screen.fill(BG)
    draw_edges(screen, camera)
    draw_stations(screen, camera)
    for tr in trains:
        tr.draw(screen, camera)
    for name, node in nodes.items():
        draw_node(screen, name, node, camera)
    detect_collisions(trains, screen, camera)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()

