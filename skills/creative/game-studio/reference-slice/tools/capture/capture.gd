extends Node3D
## Deterministic acceptance-capture harness. Instances the real Main scene,
## lets the title render for 20 frames, then starts the run so movie-maker
## evidence contains both title and in-run frames. Not part of the game loop;
## run it with:
##   godot --path . --write-movie out/frames.png --resolution 1280x720 \
##       --quit-after 44 res://tools/capture/Capture.tscn

const MAIN_SCENE := preload("res://scenes/Main.tscn")

var _frames: int = 0


func _ready() -> void:
	process_mode = Node.PROCESS_MODE_ALWAYS
	add_child(MAIN_SCENE.instantiate())


func _process(_delta: float) -> void:
	_frames += 1
	if _frames == 20:
		var game := get_tree().get_first_node_in_group("game")
		if game and game.has_method("_start_run"):
			game.call("_start_run")
	elif _frames == 22:
		# Move the player to a scenic vantage on the south edge, facing the
		# dais, so in-run frames read the whole arena instead of the ramp.
		var player := get_tree().get_first_node_in_group("player") as Node3D
		if player:
			player.position = Vector3(0.5, 1.2, 10.5)
			player.rotation_degrees.y = 0.0
			var camera := player.get_node_or_null("Camera3D") as Camera3D
			if camera:
				camera.rotation_degrees.x = -6.0
