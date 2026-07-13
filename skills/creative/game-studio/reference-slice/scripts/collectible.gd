extends Area3D
## A pickup the player collects. Registers into the "collectibles" group so the
## game manager can count it, spins and bobs so the world reads as alive, and
## reports collection on player overlap.

var _base_y: float = 0.0
var _phase: float = 0.0


func _ready() -> void:
	add_to_group("collectibles")
	body_entered.connect(_on_body_entered)
	_base_y = position.y
	_phase = absf(position.x * 1.7 + position.z * 0.9)


func _process(delta: float) -> void:
	rotate_y(delta * 1.6)
	var t := Time.get_ticks_msec() / 1000.0
	position.y = _base_y + sin(t * 2.0 + _phase) * 0.14


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		var game := get_tree().get_first_node_in_group("game")
		if game and game.has_method("collect"):
			game.collect()
		queue_free()
