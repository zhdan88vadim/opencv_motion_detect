
<!-- 
# make gif

ffmpeg -i input.mkv -vf "fps=5,scale=420:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse" output.gif 
-->
