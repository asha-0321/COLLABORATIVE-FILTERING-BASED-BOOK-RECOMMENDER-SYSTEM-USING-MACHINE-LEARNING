import matplotlib.pyplot as plt

# Example accuracy values
users = ['User1', 'User2', 'User3', 'User4']
accuracy = [80, 85, 90, 88]

plt.figure()
plt.bar(users, accuracy)

plt.title("Recommendation Accuracy")
plt.xlabel("Users")
plt.ylabel("Accuracy %")

plt.show()