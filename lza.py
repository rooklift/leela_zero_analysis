import gofish, os, queue, re, subprocess, sys, threading, time

# -------------

leela_zero = "C:\\Programs (self-installed)\\Leela Zero\\leelaz.exe"
network_dir = "C:\\Programs (self-installed)\\Leela Zero\\networks"

network = "2e3863edbb0e18f198e2e76d50529931c17f17f01c7468c992afd9b33f4d5379"
visits = 3200

extras = "--gtp --noponder --resignpct 0 --threads 1"

hotspot_threshold = 5

debug_comms = True

# -------------

class Info:

	# We'll store moves as either None or [x,y]

	def __init__(self, node):
		self.node = node
		self.move = None
		self.best_move = None
		self.PV = None					# PV from the position before the move
		self.score_before_move = None
		self.score_after_move = None

# -------------

process = None
stderr_lines_queue = queue.Queue()


def send(msg):
	global process

	if msg.endswith("\n") == False:
		msg += "\n"
	if debug_comms:
		print("--> " + msg.strip())
	msg = bytes(msg, encoding = "ascii")
	process.stdin.write(msg)
	process.stdin.flush()


def receive_gtp():
	global process

	s = ""

	while 1:
		z = process.stdout.readline().decode("utf-8")
		if z.strip() == "":		# Blank line always means end of output (I think)
			if debug_comms:
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
	# We let this block if we haven't got a result yet.

	while 1:
		try:
			line = stderr_lines_queue.get(block = True if result is None else False)
			search = "{} ->".format(english)
			if search in line:
				result = line

		except queue.Empty:
			return result


def main():
	global process

	if len(sys.argv) == 1:
		print("Usage: {} <filename>".format(sys.argv[0]))
		sys.exit()

	root = gofish.load(sys.argv[1])

	cmd = "\"{}\" -v {} {} -w \"{}\"".format(leela_zero, visits, extras, os.path.join(network_dir, network))

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

	all_info = []
	node = root

	# Find all nodes we're going to use and store them in Info objects...

	while 1:
		all_info.append(Info(node))
		node = node.main_child()
		if node == None:
			break

	# Go through those objects and update them...

	for i, info in enumerate(all_info):
		node = info.node

		# Record actual move...

		if node.move_coords():
			info.move = node.move_coords()

		# Send any AB / AW to engine...

		for stone in node.get_all_values("AB"):
			english = gofish.english_string_from_string(stone, node.board.boardsize)
			send("play black {}".format(english))
			receive_gtp()

		for stone in node.get_all_values("AW"):
			english = gofish.english_string_from_string(stone, node.board.boardsize)
			send("play white {}".format(english))
			receive_gtp()

		# Do genmove before sending the actual move...

		# If there's a move in the node, we can use its colour. If not, we must infer colour
		# from previous moves. Note that we CANNOT use last_colour_played() if there IS a move.

		if node.move_colour():
			colour = {gofish.BLACK: "black", gofish.WHITE: "white"}[node.move_colour()]
		else:
			colour = {None: "black", gofish.BLACK: "white", gofish.WHITE: "black"}[node.last_colour_played()]

		send("genmove {}".format(colour))	# Note that the undo below expects this to always happen.
		r = receive_gtp()

		english_best = r.split()[1]
		info.best_move = gofish.point_from_english_string(english_best, node.board.boardsize)

		# Get PV and score...

		line = search_queue_for_pv(english_best)	# Get PV line from stderr

		if line:

			# The score reported by the PV is valid only BEFORE the move
			# since the actual move in the SGF may be different.

			try:
				wr = float(re.search(r"\(V: (.+)%\) \(", line).group(1))
				if colour == "white":
					wr = 100 - wr
				info.score_before_move = wr
				if i > 0:
					all_info[i - 1].score_after_move = wr
			except:
				pass

			# PV...

			try:
				pv = re.search(r"PV: (.*)$", line).group(1)
				moves_list = pv.strip().split()
				info.PV = [gofish.point_from_english_string(mv, node.board.boardsize) for mv in moves_list]
			except:
				pass

		# Undo and send actual move...

		send("undo")
		receive_gtp()

		if node.move_coords():
			english_actual = gofish.english_string_from_point(*node.move_coords(), node.board.boardsize)
			send("play {} {}".format(colour, english_actual))
			receive_gtp()

		# The previous Info now has all the info it's getting...

		if i > 1:
			do_comment(info = all_info[i - 1], parent_info = all_info[i - 2])
			if time.monotonic() - save_time > 10:
				node.save(sys.argv[1] + ".lza.sgf")
				save_time = time.monotonic()

	root.save(sys.argv[1] + ".lza.sgf")


def do_comment(info, parent_info):

	node = info.node

	if info.score_after_move is not None:
		score_string = "{0:.2f}%".format(info.score_after_move)
	else:
		score_string = "??"

	if info.score_after_move is not None and info.score_before_move is not None:
		if info.best_move != info.move:
			delta_string = "{0:.2f}%".format(info.score_after_move - info.score_before_move)
		else:
			delta_string = "( {0:.2f}% )".format(info.score_after_move - info.score_before_move)
	else:
		delta_string = "??"

	if info.best_move != info.move and info.best_move:
		prefer_string = "LZ prefers {}".format(gofish.english_string_from_point(*info.best_move, node.board.boardsize))
	else:
		prefer_string = ""

	full_string = "{}\nDelta: {}\n{}".format(score_string, delta_string, prefer_string).strip()

	node.add_to_comment_top(full_string)

	if info.score_after_move is not None and info.score_before_move is not None:
		if abs(info.score_after_move - info.score_before_move) > hotspot_threshold:
			node.set_value("HO", 1)

	if info.best_move:
		sgf_point = gofish.string_from_point(*info.best_move)
		node.add_value("TR", sgf_point)

	if info.best_move != info.move:
		var_node = parent_info.node
		for point in info.PV:
			var_node = var_node.try_move(*point)


# -------------

main()
