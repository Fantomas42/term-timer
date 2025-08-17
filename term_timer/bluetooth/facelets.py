def to_magiccube_facelets(facelets):
    for color, face in (
            ('W', 'U'), ('Y', 'D'),
            ('G', 'F'), ('O', 'L'),
    ):
        facelets = facelets.replace(face, color)

    u_face, r_face, f_face, d_face, l_face, b_face = [
        facelets[i:i + 9]
        for i in range(0, len(facelets), 9)
    ]

    return f'{u_face}{l_face}{f_face}{r_face}{b_face}{d_face}'
