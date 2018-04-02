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
from suomilog.finnish import tokenize
from .tokenutils import *

# Bittiluokka

class Bits:
	def __init__(self, bits=None):
		self.bits = bits or set()
	def bitOn(self, bit):
		self.bits.add(bit)
		return self
	def bitOff(self, bit):
		if bit in self.bits:
			self.bits.remove(bit)
		return self
	def bitsOff(self, bits):
		for bit in bits:
			self.bitOff(bit)
		return self

# Ulostulo

class FuncOutput:
	def __init__(self, f):
		self.func = f
	def eval(self, args):
		return lambda: self.func(*[arg() for arg in args])

identity = FuncOutput(lambda x: x)

# Pythoniksi muuntamista varten

def toPython(obj):
	if "toPython" in dir(obj):
		return obj.toPython()
	elif isinstance(obj, list):
		return "[" + ", ".join([toPython(val) for val in obj]) + "]"
	elif isinstance(obj, tuple):
		return "(" + ", ".join([toPython(val) for val in obj]) + ("," if len(obj) == 1 else "") + ")"
	else:
		return repr(obj)

# Olioluokka

OBJECTS = None

def saveObjects():
	global OBJECTS
	OBJECTS = {}

def getObjects():
	return OBJECTS.values()

class RObject(Bits):
	def __init__(self, rclass, name, bits=None, obj_id=None, extra=None, name_tokens=None):
		Bits.__init__(self, bits)
		if not obj_id:
			increaseCounter()
			self.id = getCounter()
		else:
			self.id = obj_id
		if OBJECTS is not None:
			OBJECTS[self.id] = self
		self.rclass = rclass
		self.data = {}
		self.extra = extra or {}
		self.name = name
		self.name_tokens = name_tokens
		if name:
			self.data["nimi koodissa"] = CLASSES["merkkijono"].newInstance().setExtra("str", name)
	def toPython(self):
		var = f'OBJECTS[{repr(self.id)}]'
		return (
			f'{var} = RObject(CLASSES[{repr(self.rclass.name)}], {repr(self.name)}, {repr(self.bits)}, {repr(self.id)}, {toPython(self.extra)})'
			+ (";GRAMMAR.parseGrammarLine('.EXPR-" + str(self.rclass.id) + " ::= " + nameToCode(self.name_tokens, bits={"$"}, rbits={"nimento", "yksikkö"})
				+ "', FuncOutput(lambda: " + var + "))" if self.name_tokens else ""),
			";".join([
				f'{var}.data[{repr(key)}] = OBJECTS[{repr(self.data[key].id)}]' for key in self.data if isinstance(self.data[key], RObject)
			] + [
				f'{var}.data[{repr(key)}] = {{ {", ".join(["OBJECTS[" + repr(keykey.id) + "]: OBJECTS[" + str(self.data[key][keykey].id) + "]" for keykey in self.data[key]])} }}'
				for key in self.data if isinstance(self.data[key], dict)
			] + [
				f'{var}.data[{repr(key)}] = {{ {", ".join(["OBJECTS[" + str(val.id) + "]" for val in self.data[key]])} }}'
				for key in self.data if isinstance(self.data[key], set)
			])
		)
	def get(self, field_name):
		if field_name not in self.data:
			for clazz in self.rclass.superclasses():
				if field_name in clazz.fields and clazz.fields[field_name]:
					self.data[field_name] = clazz.fields[field_name].default_value
					break
			else:
				self.data[field_name] = None
		return self.data[field_name]
	def set(self, field_name, val):
		self.data[field_name] = val
	def getMap(self, field_name, key_val):
		key = key_val.toKey()
		if field_name not in self.data:
			self.data[field_name] = {}
		if key not in self.data[field_name]:
			for clazz in self.rclass.superclasses():
				if field_name in clazz.fields and clazz.fields[field_name]:
					return clazz.fields[field_name].default_value
			return None
		return self.data[field_name][key]
	def setMap(self, field_name, key_val, val):
		key = key_val.toKey()
		if field_name not in self.data:
			self.data[field_name] = {}
		self.data[field_name][key] = val
	def appendSet(self, field_name, val):
		if field_name not in self.data:
			self.data[field_name] = set()
		self.data[field_name].add(val)
	def removeSet(self, field_name, val):
		if field_name not in self.data:
			return
		if val in self.data[field_name]:
			self.data[field_name].remove(val)
	def forSet(self, field_name, var_name, pattern, f):
		if field_name not in self.data:
			return
		pushScope()
		for val in self.data[field_name]:
			if pattern.matches(val):
				putVar(var_name, val)
				f()
		popScope()
	def setExtra(self, name, data):
		self.extra[name] = data
		return self
	def asString(self):
		if self.name:
			return self.name
		if "str" in self.extra:
			return self.extra["str"]
		return "[eräs " + self.rclass.name + "]"
	def toKey(self):
		if "str" in self.extra:
			return self.extra["str"]
		else:
			return self

# Luokat

class Counter:
	counter = 0

def increaseCounter():
	Counter.counter += 1

def getCounter():
	return Counter.counter

CLASSES = {}
CLASSES_IN_ORDER = []

class RClass(Bits):
	def __init__(self, name, superclass, name_tokens, class_id=None, bit_groups=None, bits=None):
		Bits.__init__(self, bits)
		
		CLASSES[name] = self
		CLASSES_IN_ORDER.append(self)
		
		if class_id:
			self.id = class_id
		else:
			increaseCounter()
			self.id = getCounter()
		self.name = name
		self.name_tokens = name_tokens
		self.superclass = superclass
		self.direct_subclasses = []
		self.fields = {}
		self.bit_groups = bit_groups or []
		self.attributePhraseAdders = []
		
		if superclass:
			self.superclass.direct_subclasses.append(self)
	def toPython(self):
		sc = "None" if self.superclass is None else f"CLASSES[{repr(self.superclass.name)}]"
		grammar = "" if self.superclass is None else f'GRAMMAR.parseGrammarLine(".EXPR-{self.superclass.id} ::= .EXPR-{self.id}{{$}}", identity)'
		return (
			f'RClass({repr(self.name)}, {sc}, {repr(self.name_tokens)}, {repr(self.id)}, {repr(self.bit_groups)}, {repr(self.bits)});{grammar}',
			";".join(f'CLASSES[{repr(self.name)}].fields[{repr(field)}] = {self.fields[field].toPythonExpr()}' for field in self.fields)
		)
	def addField(self, name, field):
		self.fields[name] = field
	def newInstance(self, name=None, bits=set(), name_tokens=None):
		return RObject(self, name, self.allBits()|bits, name_tokens=name_tokens)
	def superclasses(self):
		if self.superclass == None:
			return [self]
		else:
			return [self] + self.superclass.superclasses()
	def subclasses(self):
		ans = [self]
		for subclass in self.direct_subclasses:
			ans += subclass.subclasses()
		return ans
	def allBits(self):
		ans = set()
		for clazz in self.superclasses():
			ans.update(clazz.bits)
		return ans
	def nameToCode(self, bits):
		if self.name_tokens:
			return nameToCode(self.name_tokens, rbits={"nimento", "yksikkö"}, bits=bits)
		else:
			return self.name + "{" + ",".join(bits) + "}"

class RField:
	def __init__(self, counter, name, vtype, defa=None, is_map=False):
		self.id = counter
		self.name = name
		self.type = vtype
		self.is_map = is_map
		self.default_value = defa
	def toPythonExpr(self):
		defa = "None" if not self.default_value else f"OBJECTS[{repr(self.default_value.id)}]"
		return f'RField({repr(self.id)}, {repr(self.name)}, CLASSES[{repr(self.type.name)}], {defa}, {repr(self.is_map)})'
	def setDefaultValue(self, defa):
		self.default_value = defa
	def copy(self):
		return RField(self.id, self.name, self.type, None, self.is_map)

class RPattern(Bits):
	def __init__(self, rclass=None, bits=None, conditions=None):
		Bits.__init__(self, bits)
		self.rclass = rclass
		self.conditions = conditions or []
	def toPython(self):	
		return "RPattern(CLASSES[" + repr(self.rclass.name) + "], " + repr(self.bits) + "," + toPython(self.conditions) + ")"
	def addCondition(self, cond):
		self.conditions.append(cond)
		return self
	def newInstance(self, name):
		name_str = tokensToString(name)
		obj = self.rclass.newInstance(name=name_str, name_tokens=name, bits=self.bits)
		for cond in self.conditions:
			cond.doModify(obj)
		return obj
	def matches(self, obj):
		if self.rclass:
			if obj.rclass not in self.rclass.subclasses():
				return False
		for cond in self.conditions:
			if not cond.doCheck(obj):
				return False
		return obj.bits >= self.bits
	def type(self):
		return self.rclass or CLASSES["asia"]

class RCondition:
	def __init__(self, var, check, modify):
		self.var = var
		self.check = check
		self.modify = modify
	def toPython(self):
		return "RCondition(" + repr(self.var) + ", lambda " + self.var + ": " + self.check + ", lambda " + self.var + ": " + self.modify + ")"
	def doCheck(self, x):
		if isinstance(self.check, str):
			return eval(self.check, globals(), {self.var: x})
		else:
			return self.check(x)
	def doModify(self, x):
		if isinstance(self.modify, str):
			return eval(self.modify, globals(), {self.var: x})
		else:
			return self.modify()

# Näkyvyysalueet ja muuttujat

class RScope(Bits):
	def __init__(self):
		Bits.__init__(self)
		self.variables = {}
	def __repr__(self):
		return "Scope(" + repr(self.variables) + ")"

GLOBAL_SCOPE = RScope()
SCOPE = []
STACK = []

def pushScope():
	SCOPE.append(RScope())
def popScope():
	SCOPE.pop()
def pushStackFrame():
	STACK.append(RScope())
def popStackFrame():
	STACK.pop()
def visibleScopes():
	return [GLOBAL_SCOPE]+SCOPE+STACK[-1:]
def getVar(name):
	for scope in reversed(visibleScopes()):
		if name in scope.variables:
			return scope.variables[name]
	sys.stderr.write("Muuttujaa ei löytynyt: " + name + "(" + repr(visibleScopes()) + ")\n")
	return None
def setVar(name, val):
	scopes = visibleScopes()
	for scope in reversed(scopes):
		if name in scope.variables:
			scope.variables[name] = val
			break
	else:
		scopes[-1].variables[name] = val
def putVar(name, val):
	visibleScopes()[-1].variables[name] = val

# Toiminnot

class RAction:
	def __init__(self, name, a_id=None):
		if not a_id:
			increaseCounter()
		self.id = a_id or getCounter()
		self.name = name
		
		ACTIONS[self.id] = self
		
		self.commands = []
	def toPython(self):
		return ";".join([
			"RAction(" + repr(self.name) + ", " + repr(self.id) + ")"
		] + [
			f"GRAMMAR.parseGrammarLine('.PLAYER-CMD ::= {pattern}', FuncOutput(lambda *x: ACTIONS[{repr(self.id)}].run(x)))" for pattern in self.commands
		])
	def addPlayerCommand(self, pattern):
		self.commands.append(pattern)
	def run(self, args):
		listeners = []
		for listener in ACTION_LISTENERS:
			if listener.action is self and all([p.matches(obj) for obj, (_, p, _) in zip(args, listener.params)]):
				listeners.append(listener)
		pushScope()
		scope = SCOPE[-1]
		special_case_found = False
		for listener in sorted(listeners, key=lambda l: l.priority):
			if listener.is_general_case and special_case_found:
				continue
			if listener.is_special_case:
				special_case_found = True
			listener.run(args)
			if "stop action" in scope.bits:
				break
		popScope()

ACTIONS = {}

class RListener:
	def __init__(self, action, params, priority, is_special_case, is_general_case, body):
		self.action = action
		self.params = params
		self.priority = priority
		self.is_special_case = is_special_case
		self.is_general_case = is_general_case
		self.body = body
		ACTION_LISTENERS.append(self)
	def toPython(self):
		return "".join(['RListener(',
			'ACTIONS[', repr(self.action.id), '], ',
			toPython(self.params), ', ',
			repr(self.priority), ', ',
			repr(self.is_special_case), ', ',
			repr(self.is_general_case), ', ',
			'[', ", ".join(["lambda: " + cmd for cmd in self.body]) + ']'
			')'
		])
	def run(self, args):
		pushStackFrame()
		for i, ((c, _, _), a) in enumerate(zip(self.params, args)):
			putVar(f"_{i}", a)
		for cmd in self.body:
			if isinstance(cmd, str):
				eval(cmd)
			else:
				cmd()
			if "stop action" in SCOPE[-1].bits:
				break
		popStackFrame()

# jälkimmäinen sarake kertoo, syrjäytyvätkö tämäntyyppiset säännöt, jos toiseksi jälkimmäisessä sarakkeessa vastaava syrjäyttävä sääntö täsmää

LISTENER_PRIORITIES = [
#	 PRE       CASE     POST       PRI SPECIAL GENERAL
	("ennen", "osanto", "",        20, False,  False),
	("",      "omanto", "sijasta", 40, True,   False),
	("",      "omanto", "aikana",  50, False,  True),
	("",      "omanto", "jälkeen", 80, False,  False),
]

ACTION_LISTENERS = []

# Merkkijonon luominen

def createStringObj(x):
	return CLASSES["merkkijono"].newInstance().setExtra("str", x)

# Tulostaminen

prev_was_newline = True

def say(text):
	global prev_was_newline
	if not text:
		return
	if not prev_was_newline:
		print(" ", end="")
	print(text,end="")
	prev_was_newline = text[-1] == "\n"

# Pelin komentotulkki

def playGame(grammar):
	global prev_was_newline
	while True:
		if not prev_was_newline:
			print()
			prev_was_newline = True
		line = input(">> ")
		interpretations = grammar.matchAll(tokenize(line), "PLAYER-CMD", set())
		if len(interpretations) == 0:
			print("Ei tulkintaa.")
		elif len(interpretations) == 1:
			interpretations[0]()
		else:
			print("Löydetty", len(interpretations), "tulkintaa.")
