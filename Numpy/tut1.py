import numpy as np

my_list = [1, 2, 3, 4, 5]

my_array = np.array(my_list)
my_array = my_array * 3

# print(my_array)
# print(type(my_array))


#multidimensional array
my_list2 = [
    [ [1, 2, 3],
      [4, 5, 6]],
    [[7, 8, 9],
     [10, 11, 12]]
    ]
my_array2 = np.array(my_list2)

# print(my_array2.ndim, my_array2.shape)

# print(my_array2[0, 1, 0]) # 6

#sliceing 
arrays = np.array([
                   [1, 2, 3, 4],
                   [5, 6, 7, 8],
                   [9, 10, 11, 12],
                   [13,14,15,16]
                   
                   ])
print(arrays[2:4])
print("        ")
print(arrays[::-2])
