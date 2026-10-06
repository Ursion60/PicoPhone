# Firmware Pico 2 (port rp2) : USER_C_MODULES=/chemin/vers/phone/micropython.cmake
# Le module utilise la HAL matérielle (écran SPI ILI9341 + tactile I2C FT6336U).
add_library(usermod_phone INTERFACE)

target_sources(usermod_phone INTERFACE
    ${CMAKE_CURRENT_LIST_DIR}/modphone.c
    ${CMAKE_CURRENT_LIST_DIR}/gfx.c
    ${CMAKE_CURRENT_LIST_DIR}/font.c
    ${CMAKE_CURRENT_LIST_DIR}/font_data.c
    ${CMAKE_CURRENT_LIST_DIR}/ui.c
    ${CMAKE_CURRENT_LIST_DIR}/icons_data.c
    ${CMAKE_CURRENT_LIST_DIR}/hal_rp2.c
)

target_include_directories(usermod_phone INTERFACE ${CMAKE_CURRENT_LIST_DIR})

target_link_libraries(usermod_phone INTERFACE
    hardware_spi hardware_i2c hardware_dma hardware_pwm
)

target_link_libraries(usermod INTERFACE usermod_phone)
