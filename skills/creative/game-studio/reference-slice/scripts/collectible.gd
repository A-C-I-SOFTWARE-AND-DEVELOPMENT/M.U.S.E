extends Area3D
## A pickup the player collects. Registers into the "collectibles" group so the
## game manager can count it, and reports collection on player overlap.

func _ready() -> void:
	add_to_group("collectibles")
	body_entered.connect(_on_body_entered)


func _on_body_entered(body: Node) -> void:
	if body.is_in_group("player"):
		var game := get_tree().get_first_node_in_group("game")
		if game and game.has_method("collect"):
			game.collect()
		queue_free()
