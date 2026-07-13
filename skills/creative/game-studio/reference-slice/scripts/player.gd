extends CharacterBody3D
## First/third-person player controller for the Game Studio vertical slice.
##
## Pure GDScript, no plugins — opens and runs on a stock Godot 4.x install.
## Movement (WASD), jump (Space), mouse-look. Also demonstrates the
## "generated asset slot": at _ready() it tries to swap the placeholder hero
## prop for a runtime-loaded mesh at res://assets/prop.glb when one is
## importable, falling back to the built-in placeholder otherwise.

const SPEED := 5.0
const SPRINT_MULT := 1.65
const JUMP_VELOCITY := 4.5
const MOUSE_SENS := 0.0025

@onready var _camera: Camera3D = $Camera3D

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity", 9.8)


func _ready() -> void:
	add_to_group("player")
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_try_load_generated_prop()


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		rotate_y(-event.relative.x * MOUSE_SENS)
		if _camera:
			_camera.rotate_x(-event.relative.y * MOUSE_SENS)
			_camera.rotation.x = clamp(_camera.rotation.x, -1.4, 1.4)


func _physics_process(delta: float) -> void:
	if not is_on_floor():
		velocity.y -= _gravity * delta

	if Input.is_action_just_pressed("jump") and is_on_floor():
		velocity.y = JUMP_VELOCITY

	var speed := SPEED * (SPRINT_MULT if InputMap.has_action("sprint") and Input.is_action_pressed("sprint") else 1.0)
	var input_dir := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var direction := (transform.basis * Vector3(input_dir.x, 0.0, input_dir.y)).normalized()
	if direction:
		velocity.x = direction.x * speed
		velocity.z = direction.z * speed
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		velocity.z = move_toward(velocity.z, 0.0, speed)

	move_and_slide()


func _try_load_generated_prop() -> void:
	## The asset slot: 3d-asset-artist fills res://assets/prop.glb via the
	## asset3d_generate tool. We load it defensively so a missing import never
	## breaks the slice — the built-in placeholder prop stays if load fails.
	var path := "res://assets/prop.glb"
	if not ResourceLoader.exists(path):
		return
	var scene := load(path)
	if scene == null:
		return
	var slot := get_node_or_null("../HeroProp")
	if slot == null:
		return
	var instance: Node = null
	if scene is PackedScene:
		instance = scene.instantiate()
	elif scene is Mesh:
		var mi := MeshInstance3D.new()
		mi.mesh = scene
		instance = mi
	if instance:
		slot.add_child(instance)
