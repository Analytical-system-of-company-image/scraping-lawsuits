from parsing_lawsuits.python_callables import (calculate_grades,
                                               get_electronic_cases,
                                               get_lawsuits,
                                               preprocessing_data)

if __name__ == "__main__":
    cases = get_lawsuits("Ростикс")

    lawsuits = get_electronic_cases(cases, 5)
    digested_data = preprocessing_data(lawsuits)
    calculate_grades(digested_data, 800_000, 699_900_000)
    print("Success")
