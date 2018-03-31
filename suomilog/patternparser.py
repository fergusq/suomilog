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

class Token:
	def __init__(self, token, alternatives):
		self.token = token
		self.alternatives = alternatives
	def __repr__(self):
		return "Token(" + repr(self.token) + ", " + repr(self.alternatives) + ")"
	def __str__(self):
		return self.token + "[" + "/".join([baseform + "{" + ", ".join(bits) + "}" for baseform, bits in self.alternatives]) + "]"
	def toCode(self):
		return self.token or "/".join([baseform + "{" + ",".join(bits) + "}" for baseform, bits in self.alternatives])
	def containsMatch(self, alternatives):
		return any([any([tbf == baseform and tbits >= bits for tbf, tbits in self.alternatives]) for baseform, bits in alternatives])
	def baseform(self, *tbits):
		tbits = set(tbits)
		for baseform, bits in self.alternatives:
			if tbits <= bits:
				return baseform
		return None

class PatternRef:
	def __init__(self, name, bits):
		self.name = name
		self.bits = bits
	def __repr__(self):
		return "PatternRef(" + repr(self.name) + ", " + repr(self.bits) + ")"
	def toCode(self):
		return "." + self.name + ("{" + ",".join(self.bits) + "}" if self.bits else "")

class MultiOutput:
	def __init__(self, outputs):
		self.outputs = outputs
	def __repr__(self):
		return "MultiOutput(" + repr(self.outputs) + ")"
	def eval(self, args):
		ans = []
		for i, output in enumerate(self.outputs):
			ans.append(output.eval([arg[i] for arg in args]))
		return ans

class StringOutput:
	def __init__(self, string):
		self.string = string
	def __repr__(self):
		return "StringOutput(" + repr(self.string) + ")"
	def eval(self, args):
		ans = self.string
		for i, a in enumerate(args):
			try:
				ans = ans.replace("$"+str(i+1), a)
			except:
				print(a)
		return ans

class Grammar:
	def __init__(self, patterns=None):
		self.patterns = patterns or {}
	def print(self):
		for category in sorted(self.patterns):
			print(category, "::=")
			for pattern in self.patterns[category]:
				print(" " + pattern.toCode())
	def copy(self):
		return Grammar({name: self.patterns[name].copy() for name in self.patterns})
	def matchAll(self, tokens, category, bits):
		ans = []
		for pattern in self.patterns[category]:
			ans += pattern.match(self, tokens, bits)
		return ans
	def allowsEmptyContent(self, category):
		return any([pattern.allowsEmptyContent() for pattern in self.patterns[category]])
	def parseGrammarLine(self, line, *outputs):
		if debug_level >= 1:
			print(line)
		tokens = line.replace("\t", " ").split(" ")
		if len(tokens) > 2 and tokens[1] == "::=" and (outputs or "->" in tokens):
			end = tokens.index("->") if "->" in tokens else len(tokens)
			category = tokens[0][1:]
			words = []
			for token in tokens[2:end]:
				if "{" in token and token[-1] == "}":
					bits = set(token[token.index("{")+1:-1].split(","))
					token = token[:token.index("{")]
				else:
					bits = set()
				if token == "":
					continue
				elif token == ".":
					words.append(Token(".", []))
				elif token[0] == ".":
					words.append(PatternRef(token[1:], bits))
				elif bits:
					words.append(Token("", [(token, bits)]))
				else:
					words.append(Token(token, []))
			if category not in self.patterns:
				self.patterns[category] = []
			if "->" in tokens:
				outputs = outputs + (StringOutput(" ".join(tokens[end+1:])),)
			pattern = Pattern(category, words, MultiOutput(outputs) if len(outputs) > 1 else outputs[0])
			self.patterns[category].append(pattern)
			return pattern
		else:
			raise Exception("Syntax error on line `" + line + "'")

debug_level = 0
indent = 0

def setDebug(n):
	global debug_level
	debug_level = n

ERRORS = []

def makeErrorMessage(ref, tokens, start, length):
	line1 = ""
	line2 = ""
	line3 = ""
	for i, token in enumerate(tokens):
		inside = start < i < start+length
		char = "~" if inside else " "
		if i != 0:
			line1 += " "
			line2 += char
			if i <= start:
				line3 += " "
		line1 += token.token
		if i == start:
			line2 += "^" + "~" * (len(token.token)-1)
		else:
			line2 += char * len(token.token)
		if i < start:
			line3 += " " * len(token.token)
		elif i == start:
			line3 += "expected " + ref.toCode()
	ERRORS.append(line1 + "\n" + line2 + "\n" + line3)

class Pattern:
	def __init__(self, name, words, output):
		self.name = name
		self.words = words
		self.output = output
	def __repr__(self):
		return "Pattern(" + repr(self.name) + ", " + repr(self.words) + ", " + repr(self.output) + ")"
	def toCode(self):
		return " ".join([w.toCode() for w in self.words])# + " -> " + repr(self.output)
	def allowsEmptyContent(self):
		return False
	def match(self, grammar, tokens, bits, i=0, j=0, g=None):
		global indent
		groups = g or {w: [0, []] for w in self.words if isinstance(w, PatternRef)}
		ans = []
		while i <= len(tokens) and j <= len(self.words):
			token = tokens[i] if i < len(tokens) else Token("<END>", [])
			word = self.words[j] if j < len(self.words) else Token("<END>", [])
			if isinstance(word, PatternRef):
				ans += self.match(grammar, tokens, bits, i, j+1, {w: [groups[w][0], groups[w][1].copy()] for w in groups})
				if len(groups[word][1]) == 0:
					groups[word][0] = i
				groups[word][1].append(token)
				i += 1
			else:
				if token.token.lower() == word.token.lower() or token.containsMatch([(wbf, bits if "$" in wbits else wbits) for wbf, wbits in word.alternatives]):
					if debug_level >= 3:
						print(" "*indent+"match:", token, word, bits)
					i += 1
					j += 1
				else:
					if debug_level >= 3:
						print(" "*indent+"no match:", token, word, bits)
					return ans
		if j < len(self.words) or i < len(tokens):
			if debug_level >= 3:
				print(" "*indent+"remainder:", i, tokens, j, self.words)
			return ans
		for w in groups:
			if not groups[w][1] and not grammar.allowsEmptyContent(w.name):
				if debug_level >= 3:
					print(" "*indent+"empty group:", w, self.words, tokens)
				return ans
		
		if debug_level >= 2:
			print(" "*indent, end="")
			for w in self.words:
				print(w.name+"=["+" ".join([str(w2) for w2 in groups[w][1]])+"]" if isinstance(w, PatternRef) else str(w), end=" ")
			print()
			indent += 1
		
		args = []
		for i, w in enumerate([w for w in self.words if isinstance(w, PatternRef)]):
			match = grammar.matchAll(groups[w][1], w.name, (w.bits-{"$"})|(bits if "$" in w.bits else set()))
			if len(match) == 0:
				makeErrorMessage(w, tokens, groups[w][0], len(groups[w][1]))
			args.append(match)
		ans = ans+[self.output.eval(c) for c in itertools.product(*args)]
		
		if debug_level >= 2:
			indent -= 1
			print(" "*indent, end="")
			print("->", ans)
		
		return ans
