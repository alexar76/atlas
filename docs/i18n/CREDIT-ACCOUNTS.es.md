# ATLAS — cuentas de crédito prepago

**Idiomas:** [EN](../CREDIT-ACCOUNTS.md) · [RU](CREDIT-ACCOUNTS.ru.md) · [ES](CREDIT-ACCOUNTS.es.md) · [FR](CREDIT-ACCOUNTS.fr.md) · [ZH](CREDIT-ACCOUNTS.zh.md)

ATLAS contabiliza sus capacidades de pago (`ATLAS_PAYMENT_ENFORCED=1`) y publica una lista de
precios. Durante mucho tiempo eso fue una tienda a medias: el límite gratuito era el techo para
**todos**, y el 402 remitía a un payment channel de un Hub — lo que no sirve, porque la propia
llamada del Hub a ATLAS cae en ese mismo límite anónimo. Medido el 2026-09-12: cuatro cite-desks
que venden planes mensuales estaban limitados a cinco ejecuciones por hora entre todos sus
clientes.

Una **cuenta de crédito** es la entrada de pago. Es prepago, la emite el operador, se le cobra el
precio publicado por llamada, queda exenta del límite gratuito y nunca paga por un rechazo.

## Dos maneras de llegar a una capacidad de pago

| | Límite gratuito | Cuenta de crédito |
|---|---|---|
| Identificación | `X-AIMarket-Sandbox-Visitor` o la dirección del llamante | `X-API-Key: atls_…` |
| Techo | `max_per_caller` por `quota_window` (5 por hora por defecto) | el saldo |
| Coste | nada | el `price_per_call_usd` publicado |
| Cuando se agota | `402` con la lista de precios | `402` indicando el saldo y lo que faltaba |
| Pensado para | probar ATLAS | todo lo que revende la respuesta o depende de ella |

Un `402` está escrito para desatascar al llamante, no solo para decirle que está atascado:
lleva `price_per_call_usd`, un bloque `free_allowance` (`max`, `used`, `quota_window`, `renews`),
un bloque `credit` cuando el raíl está activo, y `how_to_continue` como lista ordenada de lo que
sí funcionaría.

Una clave no reconocida **no** es un error: la llamada vuelve al límite gratuito, el bloque
`credit` del 402 dice `recognized: false` y el operador recibe una línea de log. Una errata en la
configuración de un desk no debe parecer una caída — pero tampoco debe parecer un éxito.

## Para el comprador

Envíe la clave y lea lo que le costó la respuesta:

```bash
curl -sD /dev/stderr -X POST https://atlas.modelmarket.dev/ai-market/v2/invoke \
  -H 'X-API-Key: atls_…' -H 'Content-Type: application/json' \
  -d '{"capability_id":"atlas.watchbox.check@v1","input":{"west":-1.0,"south":51.3,"east":0.2,"north":51.6,"layers":["flood"]}}'
```

| Encabezado de respuesta | Significado |
|---|---|
| `X-Atlas-Credit-Charged-Usd` | Lo que costó esta llamada. `0.000000` en un rechazo |
| `X-Atlas-Credit-Balance-Usd` | Lo que queda después |
| `X-Atlas-Credit-Low` | `1` cuando el saldo baja a `ATLAS_CREDITS_LOW_BALANCE_USD` o menos |

Llegan en la respuesta de la misma llamada que gastó el dinero, así que vigilar el saldo no cuesta
ninguna petición extra. Una llamada no cobrada no lleva ninguno: su ausencia significa «no se
cobró», nunca «cero».

La cuenta también se puede leer directamente. Responde `404` tanto para una clave desconocida como
para una desactivada, de modo que no sirve para averiguar qué claves existen:

```bash
curl -s https://atlas.modelmarket.dev/ai-market/v2/accounts/me -H 'X-API-Key: atls_…'
```

Un comprador que funciona sin supervisión debe tratar `X-Atlas-Credit-Low` como el momento de
actuar. Cuando llega un `402`, el trabajo de su propio cliente ya ha fallado.

## Para el operador

```bash
# Emitir una cuenta. Funciona antes de activar el raíl, para repartir las claves primero.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"label":"acme","grant_usd":25}'        # api_key se devuelve UNA sola vez

# Recargar. Idempotente por `reference`: una misma factura no se abona dos veces.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/topup \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -H 'Content-Type: application/json' \
  -d '{"amount_usd":25,"reference":"inv-1043"}'

# Suspender una cuenta sin borrar su historial.
curl -sX POST https://atlas.modelmarket.dev/ai-market/v2/accounts/<id>/status \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN" -d '{"status":"disabled"}'

# Cuánto dinero de otras personas tiene el operador en total.
curl -s https://atlas.modelmarket.dev/ai-market/v2/credits/stats \
  -H "X-Atlas-Token: $ATLAS_OPERATOR_TOKEN"
```

Solo se guarda el hash de la clave. Se muestra una vez, al crearla, y no se puede recuperar —
emita una nueva.

| Interruptor | Por defecto | Qué hace |
|---|---|---|
| `ATLAS_PAYMENT_ENFORCED` | off | Contabiliza las capacidades de pago en absoluto |
| `ATLAS_CREDITS_ENABLED` | off | Acepta claves de crédito. Las cuentas se crean antes |
| `ATLAS_CREDITS_DB_PATH` | `data/atlas_credits.db` | El libro contable. En un volumen montado |
| `ATLAS_CREDITS_LOW_BALANCE_USD` | `1.00` | Umbral de saldo bajo. `0` lo silencia |

**El orden importa.** Active `ATLAS_CREDITS_ENABLED=1` **después** de que las cuentas existan y
las claves estén en manos de los compradores. Al contrario, cada comprador con una clave aún no
entregada vuelve al límite anónimo justo cuando el sistema empieza a esperar su pago.

El operador también recibe un aviso en el log, como máximo una vez cada diez minutos por cuenta,
cuando un saldo baja del umbral. Se cuenta en llamadas restantes y no solo en dólares: lo que dice
cuánto tiempo queda para reaccionar es «unas 7 llamadas más», no «$0.42».

## Qué ocurre exactamente con el dinero

- **Reservado antes del trabajo, liquidado después.** La llamada coloca un `hold` y la entrega lo
  `capture`. Cobrar antes y devolver después sería cobrar por una caída.
- **Un rechazo nunca se cobra.** Una respuesta `ok: false` con motivo libera la reserva. Una flota
  de sensores fría no cuesta nada.
- **La unidad no es el céntimo entero.** Los saldos se llevan en milicéntimos, así que unos $0.02
  publicados se cobran exactamente como $0.02 y no se redondean a favor de nadie.
- **Una petición caída no congela dinero.** Una reserva de más de diez minutos la libera un
  barrido, así que un proceso matado no le cuesta nada a su dueño.
- **Un libro contable ilegible rechaza la llamada.** Es lo contrario del contador del límite
  gratuito, que falla abierto a propósito: servir de más en una prueba es un error de redondeo,
  mientras que servir un producto de pago sin registrarlo es dinero de otra persona.
- **Un libro contable efímero impide arrancar.** Si `ATLAS_CREDITS_DB_PATH` no sobrevive a un
  redespliegue, ATLAS se detiene en lugar de aceptar prepago en un archivo que va a borrar.

Un saldo prepago es **custodia**: dinero de otra persona en manos del operador, que vale lo que
vale la palabra del operador. No hay escrow en cadena detrás ni devolución automática — ese es el
límite honesto de este raíl, y por eso las reglas del libro contable no se negocian.

## Quién lee qué

Tanto el manifest como el 402 anuncian el raíl (`credits.enabled`, `key_header`, `account_url`),
así que un comprador puede descubrirlo por su cuenta. Los desks de la familia cite-desk leen los
encabezados de respuesta y los republican en su propio `/api/public/health` bajo `supply.credit`,
junto con el vendedor al que pertenece el saldo: un desk compra a más de uno, y una cuenta sana en
ATLAS no prueba que la otra tenga fondos.
