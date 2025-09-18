import pygame, sys, json

pygame.init()
WIDTH, HEIGHT = 1024, 720
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Track Node Editor")
clock = pygame.time.Clock()
FONT = pygame.font.SysFont(None, 100)

NODE_RADIUS = 10
GRID_SIZE = 20

NODE_TYPES = ["turn", "station", "junction", "intersection"]
NODE_COLORS = [(100,100,255), (255,180,100), (100,255,100), (255,100,100)]
EDGE_COLOR = (0,0,0)
EDGE_WIDTH = 3

nodes = {}
edges = []
node_counter = 0
selected_node = None
dragging_node = None
connecting_node = None
context_menu = None  # (pos, options)
running = True

# ---------- Helpers ----------
def snap(pos):
    x, y = pos
    return (GRID_SIZE * round(x/GRID_SIZE), GRID_SIZE * round(y/GRID_SIZE))

def get_node_at(pos):
    for name, data in nodes.items():
        x,y = data["pos"]
        if (x-pos[0])**2 + (y-pos[1])**2 <= NODE_RADIUS**2:
            return name
    return None

def draw_grid():
    for x in range(0, WIDTH, GRID_SIZE):
        pygame.draw.line(screen, (200,200,200), (x,0),(x,HEIGHT))
    for y in range(0, HEIGHT, GRID_SIZE):
        pygame.draw.line(screen, (200,200,200), (0,y),(WIDTH,y))

def draw():
    screen.fill((230,230,230))
    draw_grid()
    
    # Draw edges
    for u,v in edges:
        color_u = NODE_COLORS[NODE_TYPES.index(nodes[u]["type"])]
        color_v = NODE_COLORS[NODE_TYPES.index(nodes[v]["type"])]
        color = tuple((cu+cv)//2 for cu,cv in zip(color_u,color_v))
        pygame.draw.line(screen, color, nodes[u]["pos"], nodes[v]["pos"], EDGE_WIDTH)
    
    # Draw nodes
    for name, data in nodes.items():
        color = NODE_COLORS[NODE_TYPES.index(data["type"])]
        pygame.draw.circle(screen, color, data["pos"], NODE_RADIUS)
        label = FONT.render(name, True, (0,0,0))
        screen.blit(label, (data["pos"][0]+12, data["pos"][1]-12))
    
    # Draw connecting line if in progress
    if connecting_node:
        mx, my = pygame.mouse.get_pos()
        pygame.draw.line(screen, (150,0,0), nodes[connecting_node]["pos"], snap((mx,my)), 2)
    
    # Draw context menu
    if context_menu:
        pos, options = context_menu
        w, h = 120, 20 * len(options)
        pygame.draw.rect(screen, (200,200,200), (*pos, w, h))
        pygame.draw.rect(screen, (0,0,0), (*pos, w, h), 2)
        for i, text in enumerate(options):
            lbl = FONT.render(text, True, (0,0,0))
            screen.blit(lbl, (pos[0]+5, pos[1]+5+i*20))
    
    pygame.display.flip()

# ---------- Main loop ----------
while running:
    for ev in pygame.event.get():
        if ev.type == pygame.QUIT:
            running = False
        
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            pos = snap(ev.pos)
            if ev.button == 1:  # Left click
                if context_menu:
                    # Handle menu selection
                    cx, cy = context_menu[0]
                    for i, opt in enumerate(context_menu[1]):
                        if cx <= ev.pos[0] <= cx+120 and cy+i*20 <= ev.pos[1] <= cy+(i+1)*20:
                            node_name = selected_node
                            if node_name:
                                if opt.startswith("Delete Node"):
                                    edges = [e for e in edges if node_name not in e]
                                    del nodes[node_name]
                                    selected_node = None
                                elif opt.startswith("Delete Edges"):
                                    edges = [e for e in edges if node_name not in e]
                                elif opt.startswith("Type:"):
                                    new_type = opt.split(":")[1].strip()
                                    nodes[node_name]["type"] = new_type
                            context_menu = None
                            break
                    else:
                        context_menu = None
                    continue

                node_name = get_node_at(pos)
                if node_name:
                    dragging_node = node_name
                    selected_node = node_name
                else:
                    node_name = chr(ord('A') + node_counter)
                    node_counter += 1
                    nodes[node_name] = {"pos": pos, "type": "turn"}
                    selected_node = node_name
            
            elif ev.button == 3:  # Right click: connect or context menu
                node_name = get_node_at(pos)
                if node_name:
                    selected_node = node_name
                    # Show context menu
                    options = ["Delete Node", "Delete Edges"] + [f"Type: {t}" for t in NODE_TYPES]
                    context_menu = (ev.pos, options)
                else:
                    # Connect nodes
                    node_name = get_node_at(pos)
                    if node_name:
                        if connecting_node is None:
                            connecting_node = node_name
                        else:
                            if (connecting_node, node_name) not in edges and (node_name, connecting_node) not in edges:
                                edges.append([connecting_node, node_name])
                            connecting_node = None
        
        elif ev.type == pygame.MOUSEBUTTONUP:
            if ev.button == 1:
                dragging_node = None
        
        elif ev.type == pygame.MOUSEMOTION:
            if dragging_node:
                nodes[dragging_node]["pos"] = snap(ev.pos)
        
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_s:
                data = {"nodes": nodes, "edges": edges}
                with open("nodes.json", "w") as f:
                    json.dump(data, f, indent=2)
                print("Saved nodes.json")
            if ev.key == pygame.K_ESCAPE:
                connecting_node = None
                context_menu = None

    draw()
    clock.tick(60)

pygame.quit()
sys.exit()