import constantes as c

def calculo_pot(datos):
    corriente = [datos['corriente_out_f1'],datos['corriente_out_f2'], datos['corriente_out_f3']]
    voltaje = [datos['voltaje_out_an'],datos['voltaje_out_bn'],datos['voltaje_out_cn']]
    potencia = []
    for v,a in zip(corriente,voltaje):
        aux = v*a
        potencia.append(aux)
    
    potencia_salida = 0
    for p in potencia:
        potencia_salida += p
    potencia.append(potencia_salida)
    potencia_w = potencia_salida * c.FP_OUT
    potencia.append(potencia_w)
    return potencia