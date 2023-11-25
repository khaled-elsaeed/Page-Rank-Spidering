import sqlite3

def connect_database(database_name):
    return sqlite3.connect(database_name)

def get_from_ids(cur):
    cur.execute('''SELECT DISTINCT from_id FROM Links''')
    return [row[0] for row in cur]

def get_to_ids_and_links(cur, from_ids):
    to_ids = []
    links = []
    
    cur.execute('''SELECT DISTINCT from_id, to_id FROM Links''')
    
    for row in cur:
        from_id, to_id = row[0], row[1]
        if from_id == to_id or from_id not in from_ids or to_id not in from_ids:
            continue
        links.append(row)
        if to_id not in to_ids:
            to_ids.append(to_id)
    
    return to_ids, links

def get_prev_ranks(cur, from_ids):
    prev_ranks = {}
    for node in from_ids:
        cur.execute('''SELECT new_rank FROM Pages WHERE id = ?''', (node, ))
        row = cur.fetchone()
        prev_ranks[node] = row[0]
    return prev_ranks

def input_iterations():
    sval = input('How many iterations:')
    return int(sval) if len(sval) > 0 else 1

def sanity_check(prev_ranks):
    if len(prev_ranks) < 1:
        print("Nothing to page rank. Check data.")
        quit()

def page_rank_iterations(cur, many, prev_ranks, to_ids, links):
    for i in range(many):
        next_ranks = {}
        total = 0.0
        for (node, old_rank) in prev_ranks.items():
            total += old_rank
            next_ranks[node] = 0.0

        for (node, old_rank) in prev_ranks.items():
            give_ids = [to_id for (from_id, to_id) in links if from_id == node and to_id in to_ids]
            if len(give_ids) < 1:
                continue
            amount = old_rank / len(give_ids)
            for node_id in give_ids:
                next_ranks[node_id] = next_ranks[node_id] + amount

        newtot = sum(next_ranks.values())
        evap = (total - newtot) / len(next_ranks)

        for node in next_ranks:
            next_ranks[node] = next_ranks[node] + evap

        prev_ranks = next_ranks

        totdiff = sum(abs(old_rank - next_ranks[node]) for node, old_rank in prev_ranks.items())
        avediff = totdiff / len(prev_ranks)
        print(i + 1, avediff)

    return next_ranks

def update_database(cur, next_ranks):
    cur.execute('''UPDATE Pages SET old_rank=new_rank''')
    for (node_id, new_rank) in next_ranks.items():
        cur.execute('''UPDATE Pages SET new_rank=? WHERE id=?''', (new_rank, node_id))

def main():
    conn = connect_database('spider.sqlite')
    cur = conn.cursor()

    from_ids = get_from_ids(cur)
    to_ids, links = get_to_ids_and_links(cur, from_ids)
    prev_ranks = get_prev_ranks(cur, from_ids)

    many = input_iterations()
    sanity_check(prev_ranks)

    next_ranks = page_rank_iterations(cur, many, prev_ranks, to_ids, links)

    print(list(next_ranks.items())[:5])

    update_database(cur, next_ranks)

    conn.commit()
    cur.close()

if __name__ == "__main__":
    main()
