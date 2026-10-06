# Build "unix" de MicroPython (simulateur PC) : USER_C_MODULES=/chemin/vers/phone
# Le module utilise la HAL SDL2 (fenêtre + souris) à la place de l'écran et du tactile.
PHONE_DIR := $(USERMOD_DIR)

SRC_USERMOD_C     += $(PHONE_DIR)/modphone.c
SRC_USERMOD_LIB_C += $(PHONE_DIR)/gfx.c $(PHONE_DIR)/font.c $(PHONE_DIR)/font_data.c \
                     $(PHONE_DIR)/ui.c $(PHONE_DIR)/icons_data.c $(PHONE_DIR)/hal_sdl.c

CFLAGS_USERMOD  += -I$(PHONE_DIR) -DPHONE_SIM=1 $(shell pkg-config --cflags sdl2)
LDFLAGS_USERMOD += $(shell pkg-config --libs sdl2)
