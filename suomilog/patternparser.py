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

import sys
import re
import itertools
from copy import deepcopy
from collections import defaultdict

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
	def bits(self):
		bits = set()
		for _, b in self.alternatives:
			bits.update(b)
		return bits

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
			var = "$"+str(i+1)
			if var not in ans:
				ans = ans.replace("$*", ",".join(args[i:]))
				break
			ans = ans.replace(var, a)
		return ans

class Grammar:
	def __init__(self, patterns=None, names=None):
		self.patterns = patterns or {}
		self.names = names or {}
	def print(self):
		for category in sorted(self.patterns):
			print(category, "::=")
			for pattern in self.patterns[category]:
				print(" " + pattern.toCode())
	def copy(self):
		return Grammar({name: self.patterns[name].copy() for name in self.patterns}, self.names.copy())
	def update(self, grammar):
		for category in grammar.patterns:
			if category in self.patterns:
				self.patterns[category] += grammar.patterns[category]
			else:
				self.patterns[category] = grammar.patterns[category].copy()
		self.names.update(grammar.names)
	def matchAll(self, tokens, category, bits):
		if category not in self.patterns:
			return []
		
		ans = []
		for pattern in self.patterns[category]:
			ans += pattern.match(self, tokens, bits)
		
		return ans
	def allowsEmptyContent(self, category):
		if category not in self.patterns:
			return False
		return any([pattern.allowsEmptyContent() for pattern in self.patterns[category]])
	def addCategoryName(self, category, name):
		self.names[category] = name
	def refToString(self, ref):
		if ref.name in self.names:
			name = self.names[ref.name]
		else:
			name = ref.name
		if ref.bits:
			name += " (" + ",".join(ref.bits) + ")"
		return name
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

def groupCauses(causes):
	a = []
	groups = defaultdict(list)
	for cause in causes:
		if cause.is_part and not cause.causesContainPartErrors():
			groups[(id(cause.grammar), cause.place_string)].append(cause)
		else:
			a.append(cause)
	
	for group in groups.values():
		refs = []
		for cause in group:
			refs += cause.refs
		a.append(ParsingError(group[0].grammar, refs, group[0].place_string, True, []))
	
	return a

class ParsingError:
	def __init__(self, grammar, refs, place_string, is_part, causes):
		self.grammar = grammar
		self.refs = refs
		self.place_string = place_string
		self.is_part = is_part
		self.causes = groupCauses(causes)
	def print(self, finnish=False, file=sys.stderr):
		global indent
		ref_str = (" tai " if finnish else " or ").join(map(self.grammar.refToString, self.refs))
		if self.is_part:
			string = ("\n"+self.place_string).replace("\n", "\n"+"  "*indent)[1:]
			if finnish:
				print(string + "tämän pitäisi olla " + ref_str, file=file)
			else:
				print(string + "expected " + ref_str, file=file)
		if self.causesContainPartErrors():
			if finnish:
				print("  "*indent+"lauseke ei voi olla "+ref_str+" koska:", file=file)
			else:
				print("  "*indent+ref_str+" does not match because:", file=file)
			indent += 1
			causes = list(filter(ParsingError.containsPartErrors, self.causes))
			for cause in causes[:5]:
				cause.print(finnish=finnish)
				print(file=file)
			if len(causes) > 5:
				if finnish:
					print("  "*indent+"+ " + str(len(self.causes)-5) + " muuta mahdollista virhettä", file=file)
				else:
					print("  "*indent+"+ " + str(len(self.causes)-5) + " more errors", file=file)
			indent -= 1
	def causesContainPartErrors(self):
		return any([cause.containsPartErrors() for cause in self.causes])
	def containsPartErrors(self):
		return self.is_part or self.causesContainPartErrors()

ERROR_STACK = [[]]

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
	return line1 + "\n" + line2 + "\n" + line3

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
			ERROR_STACK.append([])
			
			match = grammar.matchAll(groups[w][1], w.name, (w.bits-{"$"})|(bits if "$" in w.bits else set()))
			
			errors = ERROR_STACK.pop()
			if len(match) == 0:
				error = ParsingError(
					grammar,
					[w],
					makeErrorMessage(w, tokens, groups[w][0], len(groups[w][1])),
					len(groups[w][1]) != len(tokens),
					errors
				)
				ERROR_STACK[-1].append(error)
			
			args.append(match)
			
			if len(match) == 0:
				break
		ans = ans+[self.output.eval(c) for c in itertools.product(*args)]
		
		if debug_level >= 2:
			indent -= 1
			print(" "*indent, end="")
			print("->", ans)
		
		return ans
