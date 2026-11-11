import json
T = "Free on the App Store, link in bio."
P = {
 "single_steps.jpg": ("Pizza night, little chef style! 🍕 Dough, sauce, toppings, oven, slice. Following steps one at a time is a real early learning skill.", "#PofuKids #kidsapp #pretendplay #preschoolactivities #learningthroughplay"),
 "single_firewash.jpg": ("Fire truck bath time! 🚒🫧 Soap, scrub, rinse and shine. Little helpers love making things sparkle.", "#PofuKids #kidsapp #firetruck #toddleractivities #learningthroughplay"),
 "single_problem.jpg": ("Uh oh, the car broke down! 🔧 Tow it, fix it, paint it and get it back on the road. Tiny mechanics, big problem solvers.", "#PofuKids #kidsapp #problemsolving #carloverkids #learningthroughplay"),
 "single_numbers.jpg": ("Can your little one find the number 9? 🎈 Catch the right balloons and fill the truck.", "#PofuKids #kidsapp #countingforkids #preschoolactivities #earlylearning"),
 "single_egg.jpg": ("What is inside the egg? 🥚✨ Every finished game earns a star. Five stars crack open a surprise.", "#PofuKids #kidsapp #surpriseegg #toddleractivities #learningthroughplay"),
 "single_puzzle.jpg": ("Puzzle time! 🧩 Drag the pieces and watch the smiley bus appear. 56 pictures to finish.", "#PofuKids #kidsapp #puzzlesforkids #finemotorskills #learningthroughplay"),
 "single_shapetrain.jpg": ("Shapes on the move 🚂 Stars, hearts and ovals ride the Shape Express. Which wagon gets the heart?", "#PofuKids #kidsapp #learnshapes #trainsforkids #earlylearning"),
 "single_memory.jpg": ("Can you find the pairs? 🃏 Flip two cards and remember where each truck is hiding. Great for focus.", "#PofuKids #kidsapp #memorygame #constructionkids #preschoolactivities"),
}
R = {
 "reel20_feelings.mp4": ("\"Who looks sad?\" 💛 Naming feelings is a big skill for little kids, and Zuzu turns it into a game.", "#PofuKids #kidsapp #emotionsforkids #gentleparenting #preschoolactivities"),
 "reel15_burger.mp4": ("Order up! 🍔 Panda wants a burger: grill the patty, flip it, stack it, ring the bell.", "#PofuKids #kidsapp #pretendplay #kidscooking #toddleractivities"),
 "reel17_letters.mp4": ("Spin the wheel, find the letter! 🔤 Catch the right balloons and fill the truck.", "#PofuKids #kidsapp #learnletters #phonics #preschoolactivities"),
 "reel26_shapetrain.mp4": ("All aboard the Shape Express! 🚂 Star, heart, oval, diamond: drop each shape in its wagon.", "#PofuKids #kidsapp #learnshapes #trainsforkids #earlylearning"),
 "reel19_crane.mp4": ("Load each truck by color 🏗️ The crane does the lifting, your little one does the thinking.", "#PofuKids #kidsapp #learncolors #constructionkids #toddleractivities"),
 "reel16_piano.mp4": ("Tiny hands, big concert 🎹 Tap the colorful keys and play along.", "#PofuKids #kidsapp #musicforkids #kidspiano #toddleractivities"),
 "reel24_lemonade.mp4": ("One lemonade, coming right up! 🍋 Slice, squeeze, add ice and serve it to Fox.", "#PofuKids #kidsapp #pretendplay #kidscooking #preschoolactivities"),
 "reel21_moreless.mp4": ("Which robot has more? 🤖 Counting practice that doesn't feel like homework.", "#PofuKids #kidsapp #countingforkids #mathforkids #earlylearning"),
 "reel23_memory.mp4": ("Can your kid find the matching pairs? 🃏 Memory cards with diggers, tractors and trucks.", "#PofuKids #kidsapp #memorygame #constructionkids #toddleractivities"),
 "reel10_balloons.mp4": ("Pop only the color Zuzu asks for! 🎈 Colors and listening practice in one game.", "#PofuKids #kidsapp #learncolors #listeningskills #toddleractivities"),
 "reel25_garden.mp4": ("Snip, snip, grow! 🌳🍎 Prune the tree and watch the apples appear.", "#PofuKids #kidsapp #gardeningwithkids #natureforkids #preschoolactivities"),
 "reel8_shadow.mp4": ("Can your toddler guess the shadow before the answer pops up? 👀 Pause and play along!", "#PofuKids #kidsapp #matchinggame #toddleractivities #earlylearning"),
 "reel9_hideseek.mp4": ("Peekaboo! 🙈 Little friends pop out of the boxes. Tap them before they hide again.", "#PofuKids #kidsapp #peekaboo #babygames #toddleractivities"),
 "reel12_coloring.mp4": ("From blank page to a cozy blue house 🏠🎨 and a party at the end!", "#PofuKids #kidsapp #coloringforkids #kidsart #preschoolactivities"),
 "reel22_puzzle.mp4": ("Puzzle time with a smiley school bus 🚌🧩 56 pictures, from 2 to 16 pieces.", "#PofuKids #kidsapp #puzzlesforkids #finemotorskills #toddleractivities"),
}
days = [("single_steps.jpg","reel20_feelings.mp4","reel15_burger.mp4"),
        ("single_firewash.jpg","reel17_letters.mp4","reel26_shapetrain.mp4"),
        ("single_problem.jpg","reel19_crane.mp4","reel16_piano.mp4"),
        ("single_numbers.jpg","reel24_lemonade.mp4","reel21_moreless.mp4"),
        ("single_egg.jpg","reel23_memory.mp4","reel10_balloons.mp4"),
        ("single_puzzle.jpg","reel25_garden.mp4","reel8_shadow.mp4"),
        ("single_shapetrain.jpg","reel9_hideseek.mp4","reel12_coloring.mp4"),
        ("single_memory.jpg","reel22_puzzle.mp4",None)]
times = ["11:00","14:00","17:00"]
plan = []
for d, trio in enumerate(days):
    date = f"2026-11-{11+d:02d}"
    for t, f in zip(times, trio):
        if not f: continue
        cap, tags = (P if f.endswith(".jpg") else R)[f]
        assert "—" not in cap and len(tags.split()) <= 5
        plan.append({"date": date, "time": t, "file": f, "kind": "photo" if f.endswith(".jpg") else "reel",
                     "url": f"https://raw.githubusercontent.com/caltun90/pofukids-social/main/media/{f}",
                     "text": f"{cap}\n\n{T}\n\n{tags}", "buffer_id": None})
json.dump(plan, open("plan.json", "w"), indent=1, ensure_ascii=False)
print(len(plan))
