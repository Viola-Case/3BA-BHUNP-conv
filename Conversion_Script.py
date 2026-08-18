import bpy
import sys
import os

args = sys.argv[sys.argv.index('--') + 1:]
input_path = args[0]
diff_out   = args[1]
alpha_out  = args[2]

# Objects
src_obj = bpy.data.objects['3BA_full']
dst_obj = bpy.data.objects['BHUNP_full']

# Materials
src_mat = bpy.data.materials['Source']
dst_mat = bpy.data.materials['Destination']

# Nodes
src_img_node      = src_mat.node_tree.nodes['Source Image']
diffuse_bake_node = dst_mat.node_tree.nodes['Diffuse Bake Image']
alpha_bake_node   = dst_mat.node_tree.nodes['Alpha Bake Image']

# Images
src_img    = bpy.data.images['Source Image Data']
bake_diff  = bpy.data.images['Bake Diff']
bake_alpha = bpy.data.images['Bake Alpha']

bpy.context.scene.render.engine = 'CYCLES'

# Pick a GPU backend. Order is fastest-first; a backend is unusable if this
# Blender build lacks it or it reports no devices (no card, no driver).
# Override the probe with BAKE_DEVICE=OPTIX|CUDA|HIP|ONEAPI|METAL|CPU.
#
# Note: compute_device_type's enum is populated by a dynamic callback, so
# introspecting bl_rna enum_items returns an empty list — the only reliable
# test for "does this build support X" is to try the assignment. Likewise
# prefs.devices lists every detected device regardless of the selected
# backend, so get_devices_for_type() is what actually answers "is there a
# card for this backend".
def select_bake_device():
    prefs = bpy.context.preferences.addons['cycles'].preferences

    forced = os.environ.get('BAKE_DEVICE', '').strip().upper()
    if forced == 'CPU':
        print("Device: CPU (forced by BAKE_DEVICE)")
        return 'CPU'

    order = [forced] if forced else ['OPTIX', 'CUDA', 'HIP', 'ONEAPI', 'METAL']

    for backend in order:
        try:
            prefs.compute_device_type = backend
        except TypeError:
            print(f"Device: {backend} not supported by this Blender build, skipping")
            continue

        # refresh_devices() replaced get_devices() in 2.9x; keep both paths.
        if hasattr(prefs, 'refresh_devices'):
            prefs.refresh_devices()
        else:
            prefs.get_devices()

        gpus = [d for d in prefs.get_devices_for_type(backend) if d.type == backend]
        if not gpus:
            print(f"Device: {backend} available but no devices found, skipping")
            continue

        for device in prefs.devices:
            device.use = (device.type == backend)
        print(f"Device: {backend} -> {', '.join(d.name for d in gpus)}")
        return 'GPU'

    prefs.compute_device_type = 'NONE'
    for device in prefs.devices:
        device.use = False
    print("Device: no usable GPU backend found, falling back to CPU "
          "(expect a long bake)")
    return 'CPU'

bpy.context.scene.cycles.device = select_bake_device()
bpy.context.scene.cycles.samples = 1
bpy.context.scene.cycles.use_denoising = False

def set_active_bake_node(node):
    for n in dst_mat.node_tree.nodes:
        n.select = False
    node.select = True
    dst_mat.node_tree.nodes.active = node

def bake_pass(socket_index, bake_node, output_path):

    print(f"Baking socket {socket_index}, will write to {os.path.abspath(output_path)}")

    bake_node.image.pixels.foreach_set([0.0] * len(bake_node.image.pixels))
    bake_node.image.update()

    print(f"Bake alpha size: {bake_node.image.size[:]}")
    print(f"Bake alpha colorspace: {bake_node.image.colorspace_settings.name}")
    print(f"Bake alpha channels: {bake_node.image.channels}")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    links = src_mat.node_tree.links
    for link in list(links):
        if link.from_node == src_img_node:
            links.remove(link)
    
    mat_output = src_mat.node_tree.nodes['Material Output']
    links.new(src_img_node.outputs[socket_index], mat_output.inputs['Surface'])
    
    for link in src_mat.node_tree.links:
        print(f"Link: {link.from_node.name} socket {link.from_socket.name} -> {link.to_node.name} socket {link.to_socket.name}")
    
    set_active_bake_node(bake_node)
    
    bpy.ops.object.select_all(action='DESELECT')
    src_obj.select_set(True)
    bpy.context.view_layer.objects.active = dst_obj
    
    bpy.ops.object.bake(type='EMIT', use_selected_to_active=True)
    
    bake_node.image.filepath_raw = os.path.abspath(output_path)
    bake_node.image.file_format = 'PNG'
    bake_node.image.save()

# Diffuse pass
src_img.filepath = input_path
src_img.reload()
bake_pass(0, diffuse_bake_node, diff_out)

# Alpha pass — same image, just different socket
bake_pass(1, alpha_bake_node, alpha_out)