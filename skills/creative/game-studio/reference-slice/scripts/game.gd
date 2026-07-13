extends Node3D
## Game manager for the vertical slice — the complete game loop.
##
## States: TITLE -> PLAYING -> WON, with PAUSED overlaying play. Tracks the
## run timer, persists the best time to user://slice.cfg, drives the HUD
## overlays, and fires the procedural sfx. Pure GDScript, no plugins.

enum State { TITLE, PLAYING, PAUSED, WON }

@onready var _status: Label = $HUD/Status
@onready var _clock: Label = $HUD/Clock
@onready var _title_panel: Control = $HUD/TitlePanel
@onready var _pause_panel: Control = $HUD/PausePanel
@onready var _win_panel: Control = $HUD/WinPanel
@onready var _win_line: Label = $HUD/WinPanel/Center/Box/WinLine
@onready var _win_time: Label = $HUD/WinPanel/Center/Box/WinTime
@onready var _pickup_sfx: AudioStreamPlayer = $PickupSfx
@onready var _win_sfx: AudioStreamPlayer = $WinSfx
@onready var _core_light: OmniLight3D = get_node_or_null("OmniCore")

const SAVE_PATH := "user://slice.cfg"

var state: int = State.TITLE
var total: int = 0
var collected: int = 0
var run_time: float = 0.0
var best_time: float = 0.0


func _ready() -> void:
	add_to_group("game")
	process_mode = Node.PROCESS_MODE_ALWAYS
	_load_best()
	# Collectibles register themselves into the "collectibles" group on _ready;
	# defer the count one frame so they've all registered.
	call_deferred("_count_and_refresh")
	call_deferred("_enter_title")


func _process(delta: float) -> void:
	if state == State.PLAYING:
		run_time += delta
		if _clock:
			_clock.text = _format_time(run_time)
	if _core_light:
		# Slow breathing on the core light keeps the arena alive on every
		# screen, including title and pause (this node always processes).
		var t := Time.get_ticks_msec() / 1000.0
		_core_light.light_energy = 2.6 + 0.5 * sin(t * 1.3)


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"):
		if state == State.TITLE:
			_start_run()
		elif state == State.WON:
			get_tree().paused = false
			get_tree().reload_current_scene()
	elif event.is_action_pressed("pause") and state in [State.PLAYING, State.PAUSED]:
		_toggle_pause()


func collect() -> void:
	collected += 1
	if _pickup_sfx:
		_pickup_sfx.pitch_scale = 1.0 + collected * 0.06
		_pickup_sfx.play()
	_refresh()
	if total > 0 and collected >= total:
		_win()


func _enter_title() -> void:
	state = State.TITLE
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	_show_only(_title_panel)


func _start_run() -> void:
	state = State.PLAYING
	run_time = 0.0
	get_tree().paused = false
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_show_only(null)
	_refresh()


func _toggle_pause() -> void:
	if state == State.PLAYING:
		state = State.PAUSED
		get_tree().paused = true
		Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		_show_only(_pause_panel)
	elif state == State.PAUSED:
		state = State.PLAYING
		get_tree().paused = false
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
		_show_only(null)


func _win() -> void:
	state = State.WON
	get_tree().paused = true
	Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
	if _win_sfx:
		_win_sfx.play()
	var record := best_time <= 0.0 or run_time < best_time
	if record:
		best_time = run_time
		_save_best()
	if _win_line:
		_win_line.text = "All %d cores recovered." % total
	if _win_time:
		var best_text := _format_time(best_time)
		var run_text := _format_time(run_time)
		var suffix := "  — new record!" if record else "  (best %s)" % best_text
		_win_time.text = "Time %s%s" % [run_text, suffix]
	_show_only(_win_panel)


func _count_and_refresh() -> void:
	total = get_tree().get_nodes_in_group("collectibles").size()
	_refresh()


func _refresh() -> void:
	if _status:
		_status.text = "Cores: %d / %d" % [collected, total]


func _show_only(panel: Control) -> void:
	for entry in [_title_panel, _pause_panel, _win_panel]:
		if entry:
			entry.visible = entry == panel


func _format_time(value: float) -> String:
	var minutes := int(value) / 60
	var seconds := fmod(value, 60.0)
	return "%d:%05.2f" % [minutes, seconds]


func _load_best() -> void:
	var config := ConfigFile.new()
	if config.load(SAVE_PATH) == OK:
		best_time = float(config.get_value("records", "best_time", 0.0))


func _save_best() -> void:
	var config := ConfigFile.new()
	config.set_value("records", "best_time", best_time)
	config.save(SAVE_PATH)
