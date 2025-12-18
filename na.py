from sklearn.linear_model import LogisticRegression
import numpy as np
import pandas as pd
# 1. Your dataset
hours = np.array([[1], [2], [3], [4], [5]])      # input
grades = np.array([0,0,0,1,1])
income = np.array([20,30,50,60,80]) # 0:female, 1:male, 

#rades = np.array([55, 60, 65, 70, 80])  # output

# 2. Reshape hours to be 2D (scikit-learn expects X as 2D)
X = np.column_stack((hours, income))  # shape: (5, 1)
#X = hours
y = grades             
#print(X)
# 3. Create the model
model = LogisticRegression()

# 4. Train (fit) the model on X and y
model.fit(X, y)

# 5. Predict the grade for 6 hours of studying
hours_new = np.array([[5,30]])  
predicted_grade = model.predict(hours_new)

#print("If you study 7 hours, predicted grade:", predicted_grade[0])

#sets 0 to fail and 1 to pass
if predicted_grade[0]==1:
    print("PASS")
else:
    print("FAIL")
print(predicted_grade)
probs = model.predict_proba(hours_new)
# does all the probailoty stuff by setting points in array of 0 to fail_probs viceversa
fail_probs = probs[0][0]
pass_probs = probs[0][1]

print("Failed: ", round((100*fail_probs),1) , "%")
print("Passed: ", round((100*pass_probs),1), "%")





