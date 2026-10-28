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

# Option (expérimentale, non testée sur la carte) : framebuffer de 150 Ko en PSRAM au lieu de la SRAM.
#   PHONE_FB_IN_PSRAM=1 tools/build_firmware.sh        (ou -DPHONE_FB_IN_PSRAM=ON)
if(PHONE_FB_IN_PSRAM OR "$ENV{PHONE_FB_IN_PSRAM}" STREQUAL "1")
    target_compile_definitions(usermod_phone INTERFACE PHONE_FB_IN_PSRAM=1)
    target_link_libraries(usermod_phone INTERFACE hardware_psram)
    # Le port détecte la taille de la PSRAM à l'exécution ; le linker, lui, doit la connaître pour y placer
    # le framebuffer (région PSRAM de 0 octet sinon). La cible n'existe pas encore ici : appel différé.
    cmake_language(DEFER CALL pico_override_psram_size firmware 8388608)
endif()

target_link_libraries(usermod_phone INTERFACE
    hardware_spi hardware_i2c hardware_dma hardware_pwm
)

target_link_libraries(usermod INTERFACE usermod_phone)
