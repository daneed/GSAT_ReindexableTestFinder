import logging
import re, sys
import argparse, pathlib
import enum

class CheckType(enum.Enum):
    NORMAL =1
    DUPLICATE = 2 
    ORDER = 3

class FileChecker(object):
    def __init__(self, onlySortingProblem, detailed):
        self.mainStepRegex = re.compile (r"\s*step\s*([0-9]+)\s*;.*")
        self._logger = logging.getLogger("Checker")
        self.onlySortingProblem = onlySortingProblem
        self.detailed = detailed

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
                return self._normalCheck(filePath, encoding)
            case CheckType.ORDER:
                return self._orderCheck(filePath, encoding)
            case CheckType.DUPLICATE:
                return self._duplicatesCheck(filePath, encoding)

    def _normalCheck(self, filePath, encoding=None):
        returnValue = True
        expectedStepIndex = 0
        with open (filePath, "r", encoding=encoding) as scriptFile:
            for line in scriptFile:
                match = self.mainStepRegex.search(line)
                if (match):
                    foundStepIndex = int (match.group(1))
                    if expectedStepIndex == 0 and foundStepIndex == 1:
                        self._logger.debug ("Indexing from 1: this is legal")
                        expectedStepIndex = foundStepIndex
                    if foundStepIndex == expectedStepIndex:
                        expectedStepIndex+=1
                    else:
                        returnValue=False
                        self._logger.info(f"Checking {filePath.name} FAILED! Expected step: {expectedStepIndex}, found step: {foundStepIndex}")
                        if not self.detailed:
                            break
                        else:
                            expectedStepIndex=foundStepIndex
        return returnValue

    def _orderCheck(self, filePath, encoding=None):
        returnValue = True
        biggestLastStepIndex = None
        steps = list()
        stepsInBadPosition = list()
        with open (filePath, "r", encoding=encoding) as scriptFile:
            for line in scriptFile:
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
                 self._logger.info(f"    Steps, in order: {' '.join ([str(step) for step in steps])}")
        return returnValue

    def _duplicatesCheck(self, filePath, encoding=None):
        returnValue = True
        duplicatesDict = dict()
        duplicatesDict_lineIndices = dict()
        duplicatesDict_sortingProblem = set()
        expectedStepIndex = 0
        with open (filePath, "r", encoding=encoding) as scriptFile:
            lines = scriptFile.readlines()
            prevFoundLineIndex = None
            for lineIndex in range (len (lines)):
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
    checkTypes = [CheckType.NORMAL]
    if args.checkOrder:
        checkTypes = [CheckType.ORDER]
    elif args.checkDuplicates:
        checkTypes = [CheckType.DUPLICATE]
    else:
        checkTypes = [CheckType.ORDER,CheckType.DUPLICATE]

    checkFailedCounter = 0
    fileChecker = FileChecker (args.onlySortingProblem, args.detailed)
    for filePath in pathlib.Path(args.folder).rglob("*.pl"):
        if filePath.parent.parent.name.startswith("_"):
            continue
        returnValue = True
        for checkType in checkTypes:
            returnValue &= fileChecker.check(filePath, checkType)
        if not returnValue:
            checkFailedCounter += 1
            if args.detailed:
                fileChecker.printSteps(filePath)
            print("")
        #print(f"Test: {filePath.parent.parent.name}, Perl script: {filePath.name}")

    print (f"SUMMARY: Number of tests where any check is failed: {checkFailedCounter}")
    pass

