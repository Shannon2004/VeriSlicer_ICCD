import re

def parse_log(input_filename, output_filename):
    # Read the raw log file
    with open(input_filename, 'r') as file:
        raw_content = file.read()

    # Regex pattern to find the exact variables. 
    # \s* acts as a flexible net that catches spaces and hidden newlines (terminal wrapping).
    pattern = r"Time:\s*(\d+)\s*\|\s*clk:\s*(\d)\s*\|\s*ReadReq:\s*(\d)\s*\|\s*WriteReq:\s*(\d)\s*\|\s*ReadGrant:\s*(\d)\s*\|\s*WriteGrant:\s*(\d)"
    
    # Find all matches in the text
    matches = re.finditer(pattern, raw_content)
    
    # Write the clean matches to a new file and print them to the console
    with open(output_filename, 'w') as out_file:
        count = 0
        for match in matches:
            time, clk, read_req, write_req, read_grant, write_grant = match.groups()
            
            # Reconstruct the perfect single line
            clean_line = f"Time: {time} | clk: {clk} | ReadReq: {read_req} | WriteReq: {write_req} | ReadGrant: {read_grant} | WriteGrant: {write_grant}\n"
            
            out_file.write(clean_line)
            count += 1

# Run the parser
if __name__ == "__main__":
    parse_log("tb_with_cocotb.txt", "tb_with_cocotb_parsed.txt")
