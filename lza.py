import gofish, json, os, queue, re, subprocess, sys, threading, time

extras = "--gtp --noponder --resignpct 0 --threads 1"

# -------------

class Info:

	# We'll store moves as either None or [x,y]

	def __init__(self, node):
		self.node = node
		self.colour = None
		self.best_move = None
		self.PV = None					# PV alternative to the actual move, if any
		self.score_before_move = None
		self.score_after_move = None
		self.parent = None				# Info object of previous position

	def send_AB_AW(self):

		for stone in self.node.get_all_values("AB"):
			english = gofish.english_string_from_string(stone, self.node.board.boardsize)
			send("play black {}".format(english))
			receive_gtp()

		for stone in self.node.get_all_values("AW"):
			english = gofish.english_string_from_string(stone, self.node.board.boardsize)
			send("play white {}".format(english))
			receive_gtp()

	def send_move(self):

		if self.node.move_coords():
			english_actual = gofish.english_string_from_point(*self.node.move_coords(), self.node.board.boardsize)
			send("play {} {}".format(self.colour, english_actual))
			receive_gtp()

	def node_markup(self):
		global config

		node = self.node

		if self.score_after_move != None:
			score_string = "{0:.2f}%".format(self.score_after_move)
		else:
			score_string = "??"

		if self.score_after_move != None and self.score_before_move != None:
			if self.best_move != node.move_coords():
				delta_string = "{0:.2f}%".format(self.score_after_move - self.score_before_move)
			else:
				delta_string = "( {0:.2f}% )".format(self.score_after_move - self.score_before_move)
		else:
			delta_string = "??"

		if self.best_move != node.move_coords() and self.best_move:
			prefer_string = "LZ prefers {}".format(gofish.english_string_from_point(*self.best_move, node.board.boardsize))
		else:
			prefer_string = ""

		full_string = "{}\nDelta: {}\n{}".format(score_string, delta_string, prefer_string).strip()

		node.add_to_comment_top(full_string)

		if self.score_after_move != None and self.score_before_move != None:
			if abs(self.score_after_move - self.score_before_move) > config["hotspot_threshold"]:
				node.set_value("HO", 1)

		if self.best_move:
			sgf_point = gofish.string_from_point(*self.best_move)
			node.add_value("TR", sgf_point)

		if self.best_move != node.move_coords():

			if self.parent and self.PV:

				first_colour = {"black": gofish.BLACK, "white": gofish.WHITE}[self.colour]
				made_first = False

				var_node = self.parent.node

				for point in self.PV:
					if made_first:
						var_node = var_node.try_move(*point)
					else:
						var_node = var_node.try_move(*point, colour = first_colour)
						made_first = True

# -------------

process = None
stderr_lines_queue = queue.Queue()
config = None


def send(msg):
	global process
	global config

	if msg.endswith("\n") == False:
		msg += "\n"
	if config["debug_comms"]:
		print("--> " + msg.strip())
	msg = bytes(msg, encoding = "ascii")
	process.stdin.write(msg)
	process.stdin.flush()


def receive_gtp():
	global process
	global config

	s = ""

	while 1:
		z = process.stdout.readline().decode("utf-8")
		if z.strip() == "":		# Blank line always means end of output (I think)
			if config["debug_comms"]:
				print("<-- " + s.strip())
			return s.strip()
		s += z


def stderr_watcher():
	global process
	global stderr_lines_queue

	while 1:
		z = process.stderr.readline().decode("utf-8")
		stderr_lines_queue.put(z.strip())


def search_queue_for_pv(english):
	global stderr_lines_queue

	result = None

	# Check all lines in the queue, also removing them all from the queue.
	# We use the string "playout" as a marker for when stderr output ends.
	# This is highly fragile to future changes in LZ. It must be some string
	# that appears ONCE near the end of the output. One can't simply use
	# the search string (e.g. "C16 ->") because there will be some more
	# output after that, which might be mistaken for the PV next iteration.

	while 1:
		line = stderr_lines_queue.get(block = True)
		search = "{} ->".format(english)
		if search in line:
			result = line
		if "playout" in line:		# See above.
			return result


def analyse(colour_string, boardsize):

	send("genmove {}".format(colour_string))
	r = receive_gtp()

	english_best = r.split()[1]
	best_move = gofish.point_from_english_string(english_best, boardsize)	# Can be None

	wr = None
	pv = []

	line = search_queue_for_pv(english_best)	# Get relevant line from stderr

	if line:

		# Get winrate from line...

		try:
			wr = float(re.search(r"\(V: (.+)%\) \(", line).group(1))
			if colour_string == "white":
				wr = 100 - wr
		except:
			pass

		# Get PV from line...

		try:
			pv_string = re.search(r"PV: (.*)$", line).group(1)
			moves_list = pv_string.strip().split()
			pv = [gofish.point_from_english_string(mv, boardsize) for mv in moves_list]
		except:
			pass

	send("undo")
	receive_gtp()

	return (best_move, wr, pv)


def main():
	global process
	global config

	if len(sys.argv) == 1:
		print("Usage: {} <filename>".format(sys.argv[0]))
		sys.exit()

	root = gofish.load(sys.argv[1])

	# Find and load the config file...

	scriptpath = os.path.realpath(__file__)
	configfile = os.path.join(os.path.dirname(scriptpath), "config.json")
	with open(configfile) as cfg:
		config = json.load(cfg)

	# Start the engine...

	cmd = "\"{}\" -v {} {} -w \"{}\"".format(config["engine"], config["visits"], extras, os.path.join(config["network_dir"], config["network"]))

	process = subprocess.Popen(cmd,
		shell = False,
		stdin = subprocess.PIPE,
		stdout = subprocess.PIPE,
		stderr = subprocess.PIPE,
	)

	# Start a thread to watch stderr and put its output on a queue...
	# This allows us to search recent stderr messages without blocking.

	threading.Thread(target = stderr_watcher, daemon = True).start()

	save_time = time.monotonic()

	# Make a list of Info objects...

	all_info = []
	node = root

	while 1:

		# Totally ignore empty nodes. Everything else gets put in the list...

		if "B" in node.properties or "W" in node.properties or "AB" in node.properties or "AW" in node.properties:

			new_info = Info(node)

			if len(all_info) > 0:
				new_info.parent = all_info[-1]		# Might not correspond to the node's actual parent node (due to empty nodes)

			if node.move_colour():
				new_info.colour = {gofish.BLACK: "black", gofish.WHITE: "white"}[node.move_colour()]

			all_info.append(new_info)

		node = node.main_child()
		if node == None:
			break

	# Main loop...

	for info in all_info:

		# Send any handicap stones etc...

		info.send_AB_AW()

		# At this moment, the engine's idea of the board matches this node BEFORE the node's move.
		# We can thus get the score_before_move...

		if info.colour:
			info.best_move, info.score_before_move, info.PV = analyse(info.colour, info.node.board.boardsize)
			if info.parent:
				info.parent.score_after_move = info.score_before_move

		info.send_move()

		# The previous Info now has all the info it's getting...

		if info.parent:
			info.parent.node_markup()

		# Save often...

		if time.monotonic() - save_time > 10:
			root.save(sys.argv[1] + ".lza.sgf")
			save_time = time.monotonic()

		# Display...

		if config["showboard"]:
			info.node.board.dump(highlight = info.node.move_coords())
			print()

	# The final node needs its score_after_move before it can be marked up...

	colour = "white" if info.colour == "black" else "black"
	_, info.score_after_move, _ = analyse(colour, info.node.board.boardsize)
	info.node_markup()

	# Final save...

	root.save(sys.argv[1] + ".lza.sgf")

# -------------

main()
