from parsing_lawsuits.python_callables import (get_electronic_cases,
                                               get_lawsuits)

if __name__ == "__main__":
    cases = get_lawsuits("ДНС Ритейл")
    get_electronic_cases(cases)
