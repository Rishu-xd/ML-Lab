a = [1,2,3]
b = [4,5,6]

def add_vectors(a,b):
    assert len(a) == len(b)
    result = []
    for i,  j in zip(a,b):
        result.append(i+j)
    return result    


def subtract_vectors(a,b):
    assert len(a) == len(b)
    result = []
    for i,  j in zip(a,b):
        result.append(i-j)
    return result    




# multipliction by scalar 

def multiply_vector_by_scalar(vector, scalar):
    result = []
    for i in vector:
        result.append(i*scalar)
    return result

#NOEM

def vector_norm(vector):
    sum_of_squares = 0
    for i in vector:
        sum_of_squares += i**2
    return sum_of_squares**0.5


# Matrix addition and sutraction

matrix_a = [[1,2,3],[4,5,6]]
matrix_b = [[7,8,9],[10,11,12]]

def add_matrices(matrix_a, matrix_b):
    assert len(matrix_a) == len(matrix_b)
    result = []
    for row_a, row_b in zip(matrix_a, matrix_b):
        result_row = []
        for i, j in zip(row_a, row_b):
            result_row.append(i+j)
        result.append(result_row)
    return result



#dot products 
 


print(f"sum of the vectors is {add_vectors(a,b)}")
print(f"difference of the vectors is {subtract_vectors(a,b)}")
print(f"multiplication of the vector a by scalar 2 is {multiply_vector_by_scalar(a,2)}")
print(f"norm of the vector a is {vector_norm(a)}")
print(f"sum of the matrices is {add_matrices(matrix_a,matrix_b)}")
