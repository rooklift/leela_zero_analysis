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

	while 1:
		try:
			line = stderr_lines_queue.get(block = False)
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

	node = gofish.load(sys.argv[1])
	root = node

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

	wr_cached = None
	best_point_cached = None

	while 1:

		# If node is at end, we have nothing to do...

		child = node.main_child()
		if not child:
			break

		# If there's a move, send it to the engine...

		if node.move_coords():

			colour_foo = node.move_colour()

			if colour_foo == gofish.BLACK:
				colour = "black"
			else:
				colour = "white"

			english = gofish.english_string_from_point(*node.move_coords(), node.board.boardsize)

			send("play {} {}".format(colour, english))
			receive_gtp()

		# Also for handicap / other added stones...

		for stone in node.get_all_values("AB"):
			english = gofish.english_string_from_string(stone, node.board.boardsize)
			send("play black {}".format(english))
			receive_gtp()

		for stone in node.get_all_values("AW"):
			english = gofish.english_string_from_string(stone, node.board.boardsize)
			send("play white {}".format(english))
			receive_gtp()

		# Compare next move (found in child node) to LZ's choice...

		last_colour_foo = node.last_colour_played()

		if last_colour_foo in [gofish.WHITE, None]:
			next_colour = "black"
		else:
			next_colour = "white"

		send("genmove {}".format(next_colour))	# Note that the undo below expects this to always happen.
		r = receive_gtp()
		if debug_comms:
			print("<-- {}".format(r))

		english = r.split()[1]
		best_point = gofish.point_from_english_string(english, node.board.boardsize)

		if best_point:
			sgf_point = gofish.string_from_point(*best_point)
		else:
			sgf_point = ""

		if child.move_coords() != best_point:
			c = child.get_value("C")
			if c == None:
				child.set_value("C", "LZ prefers {}".format(english))
			else:
				child.set_value("C", "LZ prefers {}\n{}".format(english, c))

		if sgf_point:
			child.add_value("TR", sgf_point)

		# Get the PV line for the best move LZ found, from the stderr.

		line = search_queue_for_pv(english)

		if line:

			# We'll show Black's winrate in the current node.

			try:
				wr = float(re.search(r"\(V: (.+)%\) \(", line).group(1))

				# If the colour moving now (from node's position) is Black,
				# then the current Black winrate is simply the winrate of the
				# best move found. But if the move is White, the current Black
				# winrate is the "complement".

				if next_colour == "white":
					wr = 100 - wr

				c = node.get_value("C")
				if not c:
					node.set_value("C", "{0:.2f}%".format(wr))
				else:
					node.set_value("C", "{0:.2f}%\n{1}".format(wr, c))
			except:
				wr = None

			# Show change in Black winrate since last node...

			if wr is not None and wr_cached is not None:
				delta = wr - wr_cached
				if node.move_coords() != best_point_cached:
					node.add_to_comment_top("Delta: {0:.2f}%".format(delta))
				else:
					node.add_to_comment_top("Delta: ( {0:.2f}% )".format(delta))
				if abs(delta) > hotspot_threshold:
					node.set_value("HO", 1)

			# Save info to be used next iteration...

			wr_cached = wr
			best_point_cached = best_point

			# Also, send the PV to variations...

			try:
				pv = re.search(r"PV: (.*)$", line).group(1)
				moves_list = pv.strip().split()
				points_list = [gofish.point_from_english_string(mv, node.board.boardsize) for mv in moves_list]

				if points_list[0] != child.move_coords():

					next_node = node

					for point in points_list:
						next_node = next_node.try_move(*point)
			except:
				pass

		send("undo")	# Undo the genmove. Since we always genmove, always undo.
		receive_gtp()

		next_node = node.main_child()

		if not next_node:
			break

		node = next_node

		if time.monotonic() - save_time > 10:
			node.save(sys.argv[1] + ".lza.sgf")
			save_time = time.monotonic()

	node.save(sys.argv[1] + ".lza.sgf")

# -------------

main()
