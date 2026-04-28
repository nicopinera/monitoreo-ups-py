import constantes as c

def calculo_pot(datos):
    ## CALCULA LA CORRIENTE TRIFASICA
    corriente = [datos['corriente_out_f1'],datos['corriente_out_f2'], datos['corriente_out_f3']]
    voltaje = [datos['voltaje_out_an'],datos['voltaje_out_bn'],datos['voltaje_out_cn']]
    potencia = []

# Hace una lista con la potencia de cada fase quedando ej{220,220,219}
    for v,a in zip(corriente,voltaje):
        aux = v*a
        potencia.append(aux)

#Pone el valor de la suma de las potencias por el factor de potencia -
# -al final de la lista potencia ej{220,220,219, 5550}
    potencia_salida = 0
    for p in potencia:
        potencia_salida += p
    potencia.append(potencia_salida)
    potencia_w = potencia_salida * c.FP_OUT
    potencia.append(potencia_w)
    return potencia