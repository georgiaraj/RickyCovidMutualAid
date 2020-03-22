from postcodes import *
volunteer_postcodes = ['WD3 1AB', 'WD3 5HZ', 'WD3 9TR', 'WD3 9UB', 'WD3 8QQ', 'WD3 7ES', 'WD3 7NR', 'WD3 9SL', 'WD3 1BL', 'WD3 7PP', 'WD3 1HX', 'WD3 1HW', 'WD3 4EA', 'WD3 1HH', 'WD3 5AZ', 'WD3 7PR', 'WD3 4BN', 'WD3 4HG', 'WD3 4DH', 'WD3 3DN', 'WD3 7EN', 'WD3 8BS', 'WD3 8HD', 'WD3 7AY', 'WD3 7PN', 'WD3 1BN', 'WD3 1EW', 'WD3 4JZ', 'WD3 8QW', 'WD3 3EN', 'WD3 4ER', 'WD3 4JR', 'WD3 8QW', 'WD3 8GN', 'WD3 1BD', 'WD3 7NW', 'WD3 7PH', 'WD3 1BP', 'WD3 4EL', 'WD3 9SL', 'WD3 1AE', 'WD3 8QP', 'WD3 1AB', 'WD3 8JE', 'WD3 3AU', 'WD3 8PT', 'WD3 4EA', 'WD3 7BZ', 'WD3 7EN', 'WD3 1JJ', 'WD3 1QQ', 'WD3 4DU', 'WD3 4HW', 'WD3 8BP', 'WD3 7EJ', 'WD3 7AL', 'WD3 1BA', 'WD3 4AS', 'WD3 3DN', 'WD3 7DD', 'WD3 4AS', 'WD3 7EJ', 'WD3 8HU', 'WD3 8EF']
goods, bads = postcodes_data(volunteer_postcodes + ['bad_postcode'])
f = plot_locations(goods.longitude, goods.latitude, jitter=30, zoom=15,
                   save_file='volunteer-distribution.pdf')
plt.show()
