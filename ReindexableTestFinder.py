import logging
import re, sys
import argparse, pathlib
import enum

class CheckType(enum.Enum):
    NORMAL =1
    DUPLICATE = 2 
    ORDER = 3

class FileChecker(object):
    def __init__(self, onlySortingProblem, detailed, checkStepsCalledFromSubs):
        self.mainStepRegex = re.compile(r"^\s*step\s*([0-9]+)\s*;.*")
        self.subStartRegex = re.compile(r"^\s*sub\s+(.*)\s*")
        self._logger = logging.getLogger("Checker")
        self.onlySortingProblem = onlySortingProblem
        self.detailed = detailed
        self.checkStepsCalledFromSubs = checkStepsCalledFromSubs

    def check(self, filePath, checkType):
        self._logger.debug(f"Checking {filePath.name}...")
        self._logger.debug(f"Checking {filePath.name}...DONE")
        try:
            return self._checkWithEncoding(filePath, checkType, encoding="utf-8")
        except:
            return self._checkWithEncoding(filePath, checkType)
        
    def printSteps(self, filePath):
        try:
            return self._printStepsWithEncoding(filePath, encoding="utf-8")
        except:
            return self._printStepsWithEncoding(filePath)

    def _printStepsWithEncoding(self, filePath, encoding=None):
        steps = list()
        with open (filePath, "r", encoding=encoding) as scriptFile:
            for line in scriptFile:
                match = self.mainStepRegex.search(line)
                if (match):
                    foundStepIndex = int (match.group(1))
                    steps.append(foundStepIndex)
        self._logger.info(f"    Steps: {steps}")
    
    def _checkWithEncoding(self, filePath, checkType, encoding=None):
        match checkType:
            case CheckType.NORMAL:
                return self._normalCheck(filePath, encoding, self.checkStepsCalledFromSubs)
            case CheckType.ORDER:
                return self._orderCheck(filePath, encoding)
            case CheckType.DUPLICATE:
                return self._duplicatesCheck(filePath, encoding)
            
    class SubDescriptor (object):
        def __init__(self, name, level):
            self.name = name
            self.curvyBraceLevel = level
            
    def _initSubChecking(self):
        self.curvyBraceOpeningFound = False
        self.curvyBraceClosingFound = False
        self.currentCurvyBraceLevel = 0
        self.currentSingleApostropheLevel = 0
        self.currentDoubleApostropheLevel = 0
        self.subLevel = 0
        self.subStarted = False
        self.subStack = list () # maintaining the {} level, at start of a sub.

    def _checkSub(self, line):
        match = self.subStartRegex.search(line)
        justWentIntoSub = False
        if match:
            self.subStarted = True
            justWentIntoSub = True
            self.subStack.append(FileChecker.SubDescriptor (match.group(1), self.currentCurvyBraceLevel))

        if self.subLevel > 0 or self.subStarted:
            self._processSpecialCharactersInLineInsideSub (line)
            if self.subStarted and self.curvyBraceOpeningFound:
                self.curvyBraceOpeningFound = False
                self.subLevel += 1
                self.subStarted = False
            elif not self.subStarted and self.currentCurvyBraceLevel == self.subStack[-1].curvyBraceLevel:
                self.subStack.pop()
                self.subLevel -= 1
                return True

            if justWentIntoSub:
                return True
        return False
            
    def _processSpecialCharactersInLineInsideSub(self, line):
        def _characterIsEscaped(line, index):
            if index == 0:
                return False
            elif index == 1 and line[index - 1] == '\\':
                return True
            elif index > 1 and line[index - 1] == '\\' and line[index - 2] != '\\':
                return True
            else:
                return False

        for index in range (len (line)):
            if line[index] == '\'' and not _characterIsEscaped(line, index):
                if self.currentDoubleApostropheLevel == 0:
                    self.currentSingleApostropheLevel = (self.currentSingleApostropheLevel + 1) % 2
            elif line[index] == '\"' and not _characterIsEscaped(line, index):
                if self.currentSingleApostropheLevel == 0:
                    self.currentDoubleApostropheLevel = (self.currentDoubleApostropheLevel + 1) % 2
            elif line[index] == '#':
                if self.currentSingleApostropheLevel == 0 and self.currentDoubleApostropheLevel == 0:
                    break
            elif line[index] == '{' and not _characterIsEscaped(line, index):
                if self.currentSingleApostropheLevel == 0 and self.currentDoubleApostropheLevel == 0:
                    self.curvyBraceOpeningFound = True
                    self.currentCurvyBraceLevel += 1
            elif line[index] == '}' and not _characterIsEscaped(line, index):
                if self.currentSingleApostropheLevel == 0 and self.currentDoubleApostropheLevel == 0:
                    self.currentCurvyBraceLevel -= 1

    def _normalCheck(self, filePath, encoding=None, checkOnlyStepsCalledFromSubs=False):
        returnValue = True
        expectedStepIndex = 0
        expectedSteps = list()
        unexpectedSteps = list()
        stepsCalledFromSubs = list()

        self._initSubChecking()

        with open (filePath, "r", encoding=encoding) as scriptFile:
            for line in scriptFile:
                if self._checkSub(line):
                    continue

                match = self.mainStepRegex.search(line)
                if (match):
                    foundStepIndex = int (match.group(1))
                    if self.subLevel > 0:
                        returnValue=False
                        stepsCalledFromSubs.append(foundStepIndex)
                        if not self.detailed:
                            break
                        else:
                            continue

                    if expectedStepIndex == 0 and foundStepIndex == 1:
                        self._logger.debug ("Indexing from 1: this is legal")
                        expectedStepIndex = foundStepIndex
                    if foundStepIndex == expectedStepIndex:
                        expectedStepIndex+=1
                    else:
                        expectedSteps.append(expectedStepIndex)
                        unexpectedSteps.append(foundStepIndex)
                        returnValue=False
                        if not self.detailed:
                            break
                        else:
                            expectedStepIndex=foundStepIndex
            if not returnValue:
                if not checkOnlyStepsCalledFromSubs or (checkOnlyStepsCalledFromSubs and len(stepsCalledFromSubs) > 0):
                    self._logger.info(f"Checking {filePath.name} CONTINUITY CHECK FAILED!")
                if self.detailed:
                    if len(unexpectedSteps) > 0 and not checkOnlyStepsCalledFromSubs:
                        self._logger.info(f"    Incountinous steps: {' '.join ([str(step) for step in unexpectedSteps])}")
                    if len(stepsCalledFromSubs) > 0:
                        self._logger.info(f"    Steps called from subs: {' '.join ([str(step) for step in stepsCalledFromSubs])}")


            return returnValue

    def _orderCheck(self, filePath, encoding=None):
        returnValue = True
        biggestLastStepIndex = None
        steps = list()
        stepsInBadPosition = list()
        self._initSubChecking()
        with open (filePath, "r", encoding=encoding) as scriptFile:
            for line in scriptFile:
                if self._checkSub(line) or self.subLevel > 0:
                    continue

                match = self.mainStepRegex.search(line)
                if (match):
                    foundStepIndex = int (match.group(1))
                    steps.append(foundStepIndex)
                    if biggestLastStepIndex is None or biggestLastStepIndex <= foundStepIndex:
                        biggestLastStepIndex = max (foundStepIndex, biggestLastStepIndex) if biggestLastStepIndex is not None else foundStepIndex
                    else:
                        stepsInBadPosition.append(foundStepIndex)
        if len(stepsInBadPosition) > 0:
             returnValue = False
             self._logger.info(f"Checking {filePath.name} ORDERCHECK FAILED! Those steps are in bad position: {' '.join ([str(step) for step in stepsInBadPosition])}")
             if self.detailed and len(steps) > 0:
                 self._logger.info(f"    Steps: {' '.join ([str(step) for step in steps])}")
        return returnValue

    def _duplicatesCheck(self, filePath, encoding=None):
        returnValue = True
        duplicatesDict = dict()
        duplicatesDict_lineIndices = dict()
        duplicatesDict_sortingProblem = set()
        expectedStepIndex = 0
        self._initSubChecking()
        with open (filePath, "r", encoding=encoding) as scriptFile:
            lines = scriptFile.readlines()
            prevFoundLineIndex = None
            for lineIndex in range (len (lines)):
                if self._checkSub(lines[lineIndex]) or self.subLevel > 0:
                    continue

                match = self.mainStepRegex.search(lines[lineIndex])
                if (match):
                    foundStepIndex = int (match.group(1))
                    if expectedStepIndex == 0 and foundStepIndex == 1:
                        self._logger.debug ("Indexing from 1: this is legal")
                        expectedStepIndex = foundStepIndex
                    key = foundStepIndex
                    if key in duplicatesDict:
                        duplicatesDict[key] += 1
                        if prevFoundLineIndex is not None and prevFoundLineIndex > duplicatesDict_lineIndices[key][-1] and lineIndex > prevFoundLineIndex:
                            duplicatesDict_sortingProblem.add(key)
                        duplicatesDict_lineIndices[key].append(lineIndex)
                    else:
                        duplicatesDict[key] = 1
                        duplicatesDict_lineIndices[key] = [lineIndex]
                    prevFoundLineIndex = lineIndex
        reducedDuplicatesDict = {k:v for k,v in duplicatesDict.items() if v > 1}
        if len(reducedDuplicatesDict) > 0 and (not self.onlySortingProblem or len(duplicatesDict_sortingProblem) > 0):
            returnValue = False
            self._logger.info (f"Checking {filePath.name} DUPLICATES CHECK FAILED! Duplicate steps with multiplicity: {reducedDuplicatesDict}")
            if self.detailed and len(duplicatesDict_sortingProblem) > 0:
                 self._logger.info(f"    Duplicate steps in not good order-position: {sorted (duplicatesDict_sortingProblem)}")
        return returnValue

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("--folder", required=True)
    parser.add_argument("--verbose", required=False, action="store_true")
    parser.add_argument("--detailed", required=False, action="store_true")
    parser.add_argument("--checkNormal", required=False, action="store_true")
    parser.add_argument("--checkStepsCalledFromSubs", required=False, action="store_true")
    parser.add_argument("--checkOrder", required=False, action="store_true")
    parser.add_argument("--checkDuplicates", required=False, action="store_true")
    parser.add_argument("--checkAll", required=False, action="store_true")
    parser.add_argument("--onlySortingProblem", required=False, action="store_true")
    args = parser.parse_args()
    if not pathlib.Path(args.folder).is_dir():
        raise Exception("parameter should be a folder!")
    
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG if args.verbose else logging.INFO)
    logger = logging.getLogger("Checker")

    checkTypes = list()
    if not (args.checkNormal or args.checkOrder or args.checkDuplicates or args.checkAll):
        checkTypes = [CheckType.NORMAL]
    elif args.checkAll:
        checkTypes = [CheckType.NORMAL, CheckType.ORDER, CheckType.DUPLICATE]
    else:
        if args.checkNormal:
            checkTypes.append (CheckType.NORMAL)
        if args.checkOrder:
            checkTypes.append (CheckType.ORDER)
        if args.checkDuplicates:
            checkTypes.append (CheckType.DUPLICATE)

    checkFailedCounter = 0
    fileChecker = FileChecker (args.onlySortingProblem, args.detailed, args.checkStepsCalledFromSubs)
    for filePath in pathlib.Path(args.folder).rglob("*.pl"):
        if filePath.parent.parent.name.startswith("_"):
            continue
        returnValue = True
        for checkType in checkTypes:
            returnValue &= fileChecker.check(filePath, checkType)
        if not returnValue:
            checkFailedCounter += 1
            if args.detailed and not args.checkStepsCalledFromSubs:
                fileChecker.printSteps(filePath)
                print("")
        #print(f"Test: {filePath.parent.parent.name}, Perl script: {filePath.name}")

    print (f"SUMMARY: Number of tests where any check is failed: {checkFailedCounter}")
    pass

