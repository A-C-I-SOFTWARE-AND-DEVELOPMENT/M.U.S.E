extends Node3D
## Game manager for the vertical slice — the actual game loop.
##
## Counts the collectibles in the level, tracks the player's progress on the
## HUD, and declares a win when all are collected. Pure GDScript, no plugins.

@onready var _label: Label = $HUD/Status

var total: int = 0
var collected: int = 0


func _ready() -> void:
	add_to_group("game")
	# Collectibles register themselves into the "collectibles" group on _ready;
	# defer the count one frame so they've all registered.
	call_deferred("_count_and_refresh")


func _count_and_refresh() -> void:
	total = get_tree().get_nodes_in_group("collectibles").size()
	_refresh()


func collect() -> void:
	collected += 1
	_refresh()
	if total > 0 and collected >= total:
		if _label:
			_label.text = "All %d collected — you win!" % total


func _refresh() -> void:
	if _label:
		_label.text = "Collected: %d / %d" % [collected, total]
