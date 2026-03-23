data = Hash.new # Key = sorted chars of string
# Read input files relative to this script directory
SCRIPT_DIR = __dir__

#Read the wordlist and sort the characters
File.open(File.join(SCRIPT_DIR, 'wordlist.txt')).each do |line|
 line.strip!
 sorted = line.chars.sort.join
 data [sorted] = line
end
#Read the words to descramble
#Output a comma-separated list of the scrambled words
File.open(File.join(SCRIPT_DIR, 'words.txt')).each do |line|
 line.strip!
 print data[line.chars.sort.join]+","
end
#Print a final newline to make copynpaste faster
print "\n"