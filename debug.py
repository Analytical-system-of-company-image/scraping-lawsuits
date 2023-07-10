from parsing_lawsuits.python_callables import (get_electronic_cases,
                                               get_lawsuits, lawsuits_to_dataframe, preprocessing_data)

if __name__ == "__main__":
    cases = get_lawsuits("Ростикс")

    lawsuits = get_electronic_cases(cases, 5)
    df = lawsuits_to_dataframe(lawsuits)

    preprocessing_data(df)