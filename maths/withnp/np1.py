import numpy  as np

a = np.array([1, 2,3])
b = np.array([4, 5,6])

matrix_a = np.array([[1,2,3],[4,5,6]])
matrix_b = np.array([[7,8,9],[10,11,12]])



#matrix transpose 
print(f"transpose of the matrix_a is {np.transpose(matrix_a)}")


print(f"sum of the vectors is {np.add(a,b)}")
print(f"difference of the vectors is {np.subtract(a,b)}")
print(f"multiplication of the vector a by scalar 2 is {np.multiply(a,2)}")
print(f"norm of the vector a is {np.linalg.norm(a)}")
print(f"sum of the matrices is {np.add(matrix_a,matrix_b)}")