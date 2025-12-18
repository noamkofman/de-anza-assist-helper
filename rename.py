import pandas as pd
# acess csv file of requiremnts for cc to uc
pf = pd.read_csv("assist_deanza_to_ucs_mappings2.csv")
print(pf.columns)
# the columns of dataset: 
# Index(['academicYearId', 'sendingCollege', 'receivingUniversity', 'major',
#        'requirement_title', 'for_course', 'deanza_equiv'],
#       dtype='object')


# asks user for there major
user_major = input("Your Major: ")

pf["deanza_equiv"] = (pf["deanza_equiv"].astype(str).str.replace(r"\s+(and|or)\s+", ", ", regex=True))

# filters reuiremnts by major
filterd_pf1 = (pf.loc[pf['receivingUniversity'] == 'UC Santa Barbara'])
filterd_pf2 = (filterd_pf1.loc[pf['major'] == 'Statistics and Data Science, B.S.'])
# Set options to display unlimited rows and columns
for x in filterd_pf2['deanza_equiv']:
    print(x)
# print(filterd_pf2['requirement_title'])
# print(filterd_pf2['for_course'])
# print(filterd_pf2['deanza_equiv'])

#print(pf)
#rint(filterd_pf2['requirements'])

#pf.info()
