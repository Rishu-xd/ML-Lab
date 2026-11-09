import numpy as np

# my_list = [1, 2, 3, 4, 5]

# my_array = np.array(my_list)
# my_array = my_array * 3

# # print(my_array)
# # print(type(my_array))


# #multidimensional array
# my_list2 = [
#     [ [1, 2, 3],
#       [4, 5, 6]],
#     [[7, 8, 9],
#      [10, 11, 12]]
#     ]
# my_array2 = np.array(my_list2)

# print(my_array2.ndim, my_array2.shape)

# print(my_array2[0, 1, 0]) # 6

#sliceing 
# arrays = np.array([
#                    [1, 2, 3, 4],
#                    [5, 6, 7, 8],
#                    [9, 10, 11, 12],
#                    [13,14,15,16]
                   
#                    ])

#row sallection 
# print(arrays[2:4])
# print("        ")
# print(arrays[::-2])

#column selection
# print(arrays[:, 1:3])

#arithmetics 
# some  =  arrays[0:3, 0:3]
# print(some*2)
# print(some**5) 

# print(np.sqrt(some))

# arrays3  = np.array([1.5,2.05,3.001,1.999])

# print(np.round(arrays3))

# radii  = np.array([0, 1, 2, 3])

# print(np.pi * radii ** 2)

# ELEMETWISE OPERATIONS
# array1 = np.array([1,2,3])
# array2 = np.array([4,5,6])

# print(array1 + array2)
# print(array1 - array2)
# print(array1 * array2)
# print(array1 / array2)
# print(array1 ** array2)


#COMPARISON OPERATIONS
# scores = np.array([90, 80, 70, 60, 50])

# print(scores > 50)
# scores[scores < 70] = 0
# print(scores)
