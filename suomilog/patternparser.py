# Suomilog
# Copyright (C) 2018 Iikka Hauhio
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import re
import itertools
from copy import deepcopy

def parseGrammarLine(line, output=None):
	tokens = line.replace("\t", " ").split(" ")
	if len(tokens) > 2 and tokens[1] == "::=" and "->" in tokens:
		end = tokens.index("->") if not output else len(tokens)
		category = tokens[0][1:]
		words = []
		for token in tokens[2:end]:
			if "{" in token and token[-1] == "}":
				bits = set(token[token.index("{")+1:-1].split(","))
				token = token[:token.index("{")]
			else:
				bits = set()
			if token == ".":
				words.append(Token(".", {""}, set()))
			elif token[0] == ".":
				words.append(PatternRef(token[1:], bits))
			elif bits:
				words.append(Token("", {token}, bits))
			else:
				words.append(Token(token, {""}, set()))
		if category not in PATTERNS:
			PATTERNS[category] = []
		pattern = Pattern(category, words, output if output else StringOutput(" ".join(tokens[end+1:])))
		PATTERNS[category].append(pattern)
		return pattern
	else:
		raise Exception("Syntax error on line `" + line + "'")

class Token:
	def __init__(self, token, baseforms, bits):
		if isinstance(baseforms, str):
			baseforms = {baseforms}
		self.token = token
		self.baseforms = baseforms
		self.bits = bits
	def __repr__(self):
		return "Token(" + repr(self.token) + ", " + repr(self.baseforms) + ", " + repr(self.bits) + ")"
	def __str__(self):
		return self.token + "/" + ",".join(self.baseforms) + "{" + ", ".join(self.bits) + "}"

class PatternRef:
	def __init__(self, name, bits):
		self.name = name
		self.bits = bits
	def __repr__(self):
		return "PatternRef(" + repr(self.name) + ", " + repr(self.bits) + ")"

class StringOutput:
	def __init__(self, string):
		self.string = string
	def __repr__(self):
		return "StringOutput(" + repr(self.string) + ")"
	def eval(self, args):
		ans = self.string
		for i, a in enumerate(args):
			ans = ans.replace("$"+str(i+1), a)
		return ans

PATTERNS = {}

DEBUG = 0
indent = 0

class Pattern:
	def __init__(self, name, words, output):
		self.name = name
		self.words = words
		self.output = output
	def __repr__(self):
		return "Pattern(" + repr(self.name) + ", " + repr(self.words) + ", " + repr(self.output) + ")"
	def match(self, tokens, bits, i=0, j=0, g=None):
		groups = g or {w: [] for w in self.words if isinstance(w, PatternRef)}
		ans = []
		while i <= len(tokens) and j <= len(self.words):
			token = tokens[i] if i < len(tokens) else Token("<END>", "<END>", set())
			word = self.words[j] if j < len(self.words) else Token("<END>", "<END>", set())
			if isinstance(word, PatternRef):
				ans += self.match(tokens, bits, i, j+1, {w: groups[w].copy() for w in groups})
				groups[word].append(token)
				i += 1
			else:
				if token.token == word.token or (token.baseforms >= word.baseforms and (token.bits >= word.bits or ("$" in word.bits and token.bits >= bits))):
					if DEBUG >= 2:
						print("match:", token, word, bits)
					i += 1
					j += 1
				else:
					if DEBUG >= 2:
						print("no match:", token, word, bits)
					return ans
		if j < len(self.words) or i < len(tokens):
			if DEBUG >= 3:
				print("remainder:", i, tokens, j, self.words)
			return ans
		for w in groups:
			if not groups[w]:
				if DEBUG >= 3:
					print("empty group:", w, self.words, tokens)
				return ans
		
		global indent
		if DEBUG >= 1:
			print(" "*indent, end="")
			for w in self.words:
				print(w.name+"=["+" ".join([str(w2) for w2 in groups[w]])+"]" if isinstance(w, PatternRef) else str(w), end=" ")
			print()
			indent += 1
		
		args = []
		for i, w in enumerate([w for w in self.words if isinstance(w, PatternRef)]):
			args.append([])
			for p in PATTERNS[w.name]:
				args[-1] += p.match(groups[w], (w.bits-{"$"})|(bits if "$" in w.bits else set()))
		ans = ans+[self.output.eval(c) for c in itertools.product(*args)]
		
		if DEBUG >= 1:
			indent -= 1
			print(" "*indent, end="")
			print("->", ans)
		
		return ans
