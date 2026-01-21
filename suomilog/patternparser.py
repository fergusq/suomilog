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

from abc import ABC, abstractmethod
import sys
import itertools
from collections import defaultdict
from typing import Any, Callable, Self, Sequence


class Token:
	def __init__(self, token: str, alternatives: list[tuple[str, set[str]]]):
		self.token = token
		self.alternatives = alternatives

	def __repr__(self) -> str:
		return "Token(" + repr(self.token) + ", " + repr(self.alternatives) + ")"

	def __str__(self) -> str:
		return self.token + "[" + "/".join([baseform + "{" + ", ".join(bits) + "}" for baseform, bits in self.alternatives]) + "]"

	def toCode(self) -> str:
		return self.token or "/".join([baseform + "{" + ",".join(bits) + "}" for baseform, bits in self.alternatives])

	def containsMatch(self, alternatives: list[tuple[str, set[str]]]) -> bool:
		return any([any([tbf == baseform and tbits >= bits for tbf, tbits in self.alternatives]) for baseform, bits in alternatives])

	def toAlternatives(self, bits: set[str]) -> list[tuple[str, set[str]]]:
		return [(wbf, (wbits-{"$"})|(bits if "$" in wbits else wbits)) for wbf, wbits in self.alternatives]

	def baseform(self, *tbits: str):
		tbits_set = set(tbits)
		for baseform, bits in self.alternatives:
			if tbits_set <= bits:
				return baseform
		return None

	def bits(self) -> set[str]:
		bits = set()
		for _, b in self.alternatives:
			bits.update(b)
		return bits


class PatternRef:
	def __init__(self, name: str, bits: set[str], unexpanded: "PatternRef | None" = None):
		self.name = name
		self.bits = bits
		self.unexpanded = unexpanded

	def __repr__(self):
		return "PatternRef(" + repr(self.name) + ", " + repr(self.bits) +  ((", unexpanded=" + repr(self.unexpanded)) if self.unexpanded else "") + ")"

	def toCode(self):
		return "." + self.name + ("{" + ",".join(self.bits) + "}" if self.bits else "")


class Output[OutputT]:
	def eval(self, args: Sequence[OutputT]) -> OutputT:
		raise NotImplementedError()


#class MultiOutput[OutputT](Output[list[OutputT]]):
#	def __init__(self, outputs: list[Output[OutputT]]):
#		self.outputs = outputs
#
#	def __repr__(self):
#		return "MultiOutput(" + repr(self.outputs) + ")"
#
#	def eval(self, args: Sequence[list[OutputT]]):
#		ans = []
#		for i, output in enumerate(self.outputs):
#			ans.append(output.eval([arg[i] for arg in args]))
#		return ans


class StringOutput(Output[str]):
	def __init__(self, string: str):
		self.string = string

	def __repr__(self):
		return "StringOutput(" + repr(self.string) + ")"

	def eval(self, args):
		args = [arg.token if isinstance(arg, Token) else str(arg) for arg in args]
		ans = self.string
		for i, a in enumerate(args):
			var = "$"+str(i+1)
			if var not in ans:
				ans = ans.replace("$*", ",".join(args[i:]))
				break
			ans = ans.replace(var, str(a))
		return ans


class Grammar[OutputT]:
	def __init__(self, patterns: dict[str, list["BasePattern[OutputT]"]] | None = None, names: dict[str, str] | None = None):
		self.patterns = patterns or {}
		self.names = names or {}

	def print(self):
		for category in sorted(self.patterns):
			print(category, "::=")
			for pattern in self.patterns[category]:
				print(" " + pattern.toCode())

	def copy(self):
		return Grammar({name: self.patterns[name].copy() for name in self.patterns}, self.names.copy())

	def update(self, grammar: "Grammar"):
		for category in grammar.patterns:
			if category in self.patterns:
				self.patterns[category] += grammar.patterns[category]
			else:
				self.patterns[category] = grammar.patterns[category].copy()
		self.names.update(grammar.names)

	def matchAll(self, tokens: list[Token], category: str, bits: set[str]) -> list[OutputT]:
		if category not in self.patterns:
			return []
		
		ans: list[OutputT] = []
		for pattern in self.patterns[category]:
			ans += pattern.match(self, tokens, bits)
		
		return ans

	def allowsEmptyContent(self, category: str):
		if category not in self.patterns:
			return False
		return any([pattern.allowsEmptyContent() for pattern in self.patterns[category]])

	def addCategoryName(self, category: str, name: str):
		self.names[category] = name

	def refToString(self, ref: PatternRef):
		if ref.name in self.names:
			name = self.names[ref.name]
		else:
			name = ref.name
		if ref.bits:
			name += " (" + ",".join(ref.bits) + ")"
		return name

	def parseGrammarLine(self, line: str, *outputs: Output[OutputT], default_output: Callable[[str], Output[OutputT]] | None = StringOutput):
		if debug_level >= 1:
			print(line)

		tokens = line.replace("\t", " ").split(" ")
		if len(tokens) > 2 and tokens[0].startswith(".") and tokens[1] == "::=" and (outputs or "->" in tokens):
			end = tokens.index("->") if "->" in tokens else len(tokens)
			category = tokens[0][1:]
			bits = set()
			if "{" in category and category[-1] == "}":
				bits = set(",".split(category[category.index("{")+1:-1]))
				category = category[category.index("{")]
			words = []
			for token in tokens[2:end]:
				word = parseWord(token)
				if not word:
					continue
					
				words.append(word)

			if category not in self.patterns:
				self.patterns[category] = []

			if "->" in tokens:
				assert default_output is not None
				outputs = outputs + tuple(default_output(o) for o in " ".join(tokens[end+1:]).split(" &&& "))

			#pattern = Pattern(category, words, MultiOutput(list(outputs)) if len(outputs) > 1 else outputs[0], bits=bits)  # type: ignore
			assert len(outputs) == 1
			pattern = Pattern(category, words, outputs[0], bits)
			self.patterns[category].append(pattern)
			return pattern
		else:
			raise Exception("Syntax error on line `" + line + "'")

	def expandBits(self, category: str, bits: set[str], extended: dict[str, list["BasePattern[OutputT]"]] | None = None) -> dict[str, list["BasePattern[OutputT]"]]:
		if category not in self.patterns:
			return {}
		
		ans: dict[str, list[BasePattern[OutputT]]] = extended or {}
		name = "." + category + "{" + ",".join(sorted(bits)) + "}"
		if name in ans:
			return ans

		ans[name] = []
		for pattern in self.patterns[category]:
			ans[name].append(pattern.expandBits(name, self, bits, ans))
		
		return ans


def parseWord(token: str) -> Token | PatternRef | None:
	if "{" in token and token[-1] == "}":
		bits = set(token[token.index("{")+1:-1].split(","))
		token = token[:token.index("{")]
	else:
		bits = set()
	if token == "":
		return None
	elif token == ".":
		return Token(".", [])
	elif token[0] == ".":
		return PatternRef(token[1:], bits)
	elif bits:
		return Token("", [(token, bits)])
	else:
		return Token(token, [])


debug_level = 0
indent = 0

def setDebug(n: int):
	global debug_level
	debug_level = n


def groupCauses(causes: list["ParsingError"]) -> list["ParsingError"]:
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


class ParsingError[OutputT]:
	def __init__(self, grammar: Grammar[OutputT], refs: list[PatternRef], place_string: str, is_part: bool, causes: list["ParsingError"]):
		self.grammar = grammar
		self.refs = refs
		self.place_string = place_string
		self.is_part = is_part
		self.causes = groupCauses(causes)

	def print(self, finnish: bool = False, file=sys.stderr):
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


class BasePattern[OutputT](ABC):
	@abstractmethod
	def toCode(self) -> str:
		...
	
	def allowsEmptyContent(self):
		return False

	@abstractmethod
	def match(self, grammar: Grammar[OutputT], tokens: list[Token], bits: set[str]) -> list[OutputT]:
		...

	@abstractmethod
	def expandBits(self, name: str, grammar: Grammar[OutputT], bits: set[str], extended: dict[str, list["BasePattern[OutputT]"]] | None = None) -> Self:
		...


class Pattern[OutputT](BasePattern[OutputT]):
	def __init__(self, name: str, words: list[Token | PatternRef], output: Output[OutputT], bits: set[str] = set()):
		self.name = name
		self.words = words
		self.output = output
		self.bits = set(bits)
		self.positive_bits = set(bit for bit in bits if not bit.startswith("!"))
		self.negative_bits = set(bit[1:] for bit in bits if bit.startswith("!"))

	def __repr__(self):
		return "Pattern(" + repr(self.name) + ", " + repr(self.words) + ", " + repr(self.output) + ", bits=" + repr(self.bits) + ")"

	def toCode(self):
		return " ".join([w.toCode() for w in self.words])# + " -> " + repr(self.output)

	def allowsEmptyContent(self):
		return False

	def match(self, grammar: Grammar[OutputT], tokens: list[Token], bits: set[str], i=0, j=0, g=None) -> list[OutputT]:
		global indent
		groups: dict[PatternRef, list[Any]] = g or {w: [0, []] for w in self.words if isinstance(w, PatternRef)}
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
				if token.token.lower() == word.token.lower() or token.containsMatch(word.toAlternatives(bits)):
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
			print(" "*indent, self.name, (i, j), end=" ")
			for w in self.words:
				print(w.name+"=["+" ".join([str(w2) for w2 in groups[w][1]])+"]" if isinstance(w, PatternRef) else str(w), end=" ")
			print()
			indent += 1
		
		args: list[list[OutputT]] = []
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

	def expandBits(self, name: str, grammar: Grammar[OutputT], bits: set[str], extended: dict[str, list[BasePattern[OutputT]]] | None = None):
		positive_bits = set(bit for bit in bits if not bit.startswith("!"))
		negative_bits = set(bit[1:] for bit in bits if bit.startswith("!"))
		if not self.positive_bits <= positive_bits or self.negative_bits & positive_bits or self.positive_bits & negative_bits:
			return Pattern(name, [Token("<FALSE>", [])], self.output)
		
		ans = []
		for word in self.words:
			if isinstance(word, PatternRef):
				new_bits = (word.bits-{"$"})|(bits if "$" in word.bits else set())
				new_name = "." + word.name + "{" + ",".join(sorted(new_bits)) + "}"
				grammar.expandBits(word.name, new_bits, extended)
				ans += [PatternRef(new_name, set(), unexpanded=word)]
			
			elif isinstance(word, Token):
				new_alternatives = [(wbf, (wbits-{"$"})|(bits if "$" in wbits else set())) for wbf, wbits in word.alternatives]
				ans += [Token(word.token, new_alternatives)]
			
			else:
				assert False
		
		return Pattern(name, ans, self.output)