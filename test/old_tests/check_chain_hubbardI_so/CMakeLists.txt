FILE(COPY  dmft.ini DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
FILE(COPY  test.h5 DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
FILE(COPY  test.out.h5 DESTINATION ${CMAKE_CURRENT_BINARY_DIR})
FILE(COPY  test_sigma_ref.dat DESTINATION ${CMAKE_CURRENT_BINARY_DIR})

triqs_add_python_test(check_chain_hubbardI_so)
